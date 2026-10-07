/**
 * MackChainLadderEngine - Motor de Modelagem Atuarial de Provisões Técnicas
 * Implementação rigorosa do método Chain Ladder determinístico e do modelo
 * estocástico de Thomas Mack (1993) para cálculo de IBNR e erro padrão de predição.
 * 
 * Equivalência matemática exata com src/chain_ladder.py (Python).
 * Ciências Atuariais - UFMG.
 */

class MackChainLadderEngine {
  constructor(triangle, originYears = null, devPeriods = null, tailFactor = 1.0) {
    if (tailFactor < 1.0) {
      throw new Error("O fator de cauda (tailFactor) deve ser >= 1.0.");
    }
    this.tailFactor = Number(tailFactor);

    // Validação e padronização da matriz
    this.prepareData(triangle, originYears, devPeriods);

    // Atributos calculados sob demanda
    this.individualFactors = null;
    this.cumulativeFactors = null;
    this.projectedTriangle = null;
    this.ibnrSummary = null;
    this.sigmaSquared = null;
    this.originMseSummary = null;
    this.covarianceMatrix = null;
    this.totals = null;
  }

  prepareData(triangle, originYears, devPeriods) {
    if (!Array.isArray(triangle) || triangle.length === 0) {
      throw new Error("O triângulo de entrada deve ser uma matriz não vazia.");
    }

    this.nOrigins = triangle.length;
    this.nDevs = triangle[0].length;

    // Normaliza linhas para floats ou null
    this.triangleOriginal = triangle.map((row) =>
      row.map((val) => {
        if (val === null || val === undefined || isNaN(val) || val === "") {
          return null;
        }
        return Number(val);
      })
    );

    this.originYears =
      originYears && originYears.length === this.nOrigins
        ? originYears.map(String)
        : Array.from({ length: this.nOrigins }, (_, i) => `Ano ${i + 1}`);

    this.devPeriods =
      devPeriods && devPeriods.length === this.nDevs
        ? devPeriods.map(String)
        : Array.from({ length: this.nDevs }, (_, j) => `Dev ${j + 1}`);
  }

  calculateDevelopmentFactors(method = "volume_weighted") {
    const factors = [];
    const transitionNames = [];

    for (let j = 0; j < this.nDevs - 1; j++) {
      let sumCurr = 0;
      let sumNext = 0;
      let count = 0;
      let sumSimpleRatios = 0;

      for (let i = 0; i < this.nOrigins; i++) {
        const cCurr = this.triangleOriginal[i][j];
        const cNext = this.triangleOriginal[i][j + 1];

        if (cCurr !== null && cNext !== null && cCurr > 0) {
          sumCurr += cCurr;
          sumNext += cNext;
          count++;
          sumSimpleRatios += cNext / cCurr;
        }
      }

      if (count === 0) {
        throw new Error(
          `Não há pares observados para o desenvolvimento entre ${this.devPeriods[j]} e ${this.devPeriods[j + 1]}.`
        );
      }

      let fj = 1.0;
      if (method === "volume_weighted") {
        fj = sumNext / sumCurr;
      } else if (method === "simple_average") {
        fj = sumSimpleRatios / count;
      } else {
        throw new Error(`Método '${method}' não suportado.`);
      }

      factors.push(fj);
      transitionNames.push(`${this.devPeriods[j]} -> ${this.devPeriods[j + 1]}`);
    }

    this.individualFactors = {
      values: factors,
      names: transitionNames,
    };
    return this.individualFactors;
  }

  calculateCumulativeFactors() {
    if (!this.individualFactors) {
      this.calculateDevelopmentFactors();
    }

    const f = this.individualFactors.values;
    const cdf = new Array(this.nDevs).fill(0);

    // O último período recebe o fator de cauda
    cdf[this.nDevs - 1] = this.tailFactor;

    // Multiplicação acumulada reversa
    for (let j = this.nDevs - 2; j >= 0; j--) {
      cdf[j] = cdf[j + 1] * f[j];
    }

    this.cumulativeFactors = {
      values: cdf,
      periods: [...this.devPeriods],
    };
    return this.cumulativeFactors;
  }

  projectTriangle() {
    if (!this.individualFactors) {
      this.calculateDevelopmentFactors();
    }

    const f = this.individualFactors.values;
    // Cópia profunda da matriz original
    const projected = this.triangleOriginal.map((row) => [...row]);

    for (let i = 0; i < this.nOrigins; i++) {
      for (let j = 1; j < this.nDevs; j++) {
        if (projected[i][j] === null) {
          const prev = projected[i][j - 1];
          if (prev !== null) {
            projected[i][j] = prev * f[j - 1];
          }
        }
      }
    }

    this.projectedTriangle = projected;
    return this.projectedTriangle;
  }

  calculateIbnr() {
    if (!this.cumulativeFactors) {
      this.calculateCumulativeFactors();
    }
    const cdf = this.cumulativeFactors.values;

    const summary = [];
    for (let i = 0; i < this.nOrigins; i++) {
      let lastVal = 0;
      let lastDevIdx = 0;

      for (let j = this.nDevs - 1; j >= 0; j--) {
        const val = this.triangleOriginal[i][j];
        if (val !== null) {
          lastVal = val;
          lastDevIdx = j;
          break;
        }
      }

      const factorF = cdf[lastDevIdx];
      const ultimate = lastVal * factorF;
      const ibnr = ultimate - lastVal;

      summary.push({
        originIndex: i,
        originYear: this.originYears[i],
        lastObserved: lastVal,
        lastDevIdx: lastDevIdx,
        lastDevPeriod: this.devPeriods[lastDevIdx],
        factorF: factorF,
        ultimate: ultimate,
        ibnr: ibnr,
      });
    }

    this.ibnrSummary = summary;
    return this.ibnrSummary;
  }

  calculateSigmaSquared(extrapolationMethod = "mack", extrapolationValue = null) {
    if (!this.individualFactors) {
      this.calculateDevelopmentFactors();
    }

    const f = this.individualFactors.values;
    const sigmas = [];

    for (let j = 0; j < this.nDevs - 1; j++) {
      let sumCurr = 0;
      let count = 0;
      const validPairs = [];

      for (let i = 0; i < this.nOrigins; i++) {
        const cCurr = this.triangleOriginal[i][j];
        const cNext = this.triangleOriginal[i][j + 1];

        if (cCurr !== null && cNext !== null && cCurr > 0) {
          validPairs.push({ cCurr, cNext });
          sumCurr += cCurr;
          count++;
        }
      }

      const fj = f[j];
      let sigma2 = 0;

      if (count > 1) {
        let weightedResidualSum = 0;
        for (const pair of validPairs) {
          const res = pair.cNext / pair.cCurr - fj;
          weightedResidualSum += pair.cCurr * (res * res);
        }
        sigma2 = weightedResidualSum / (count - 1);
      } else {
        // Extrapolação para j com graus de liberdade = 0 (típico para j = nDevs - 2)
        if (extrapolationValue !== null && !isNaN(extrapolationValue)) {
          sigma2 = Number(extrapolationValue);
        } else if (extrapolationMethod === "mack") {
          if (Math.abs(fj - 1.0) < 1e-9) {
            sigma2 = 0.0;
          } else if (sigmas.length >= 2 && sigmas[sigmas.length - 2] > 0) {
            const sPrev2 = sigmas[sigmas.length - 2];
            const sPrev1 = sigmas[sigmas.length - 1];
            const ratio = (sPrev1 * sPrev1) / sPrev2;
            sigma2 = Math.min(ratio, Math.min(sPrev2, sPrev1));
          } else if (sigmas.length >= 1) {
            sigma2 = sigmas[sigmas.length - 1];
          } else {
            sigma2 = 0.0;
          }
        } else if (extrapolationMethod === "min") {
          if (sigmas.length >= 2) {
            sigma2 = Math.min(sigmas[sigmas.length - 1], sigmas[sigmas.length - 2]);
          } else if (sigmas.length >= 1) {
            sigma2 = sigmas[sigmas.length - 1];
          } else {
            sigma2 = 0.0;
          }
        } else if (extrapolationMethod === "log_linear") {
          const validIdx = [];
          for (let k = 0; k < sigmas.length; k++) {
            if (sigmas[k] > 0) validIdx.push(k);
          }
          if (validIdx.length >= 2) {
            const x = validIdx;
            const y = validIdx.map((k) => Math.log(sigmas[k]));
            const nPts = x.length;
            const xMean = x.reduce((a, b) => a + b, 0) / nPts;
            const yMean = y.reduce((a, b) => a + b, 0) / nPts;
            let num = 0;
            let den = 0;
            for (let idx = 0; idx < nPts; idx++) {
              num += (x[idx] - xMean) * (y[idx] - yMean);
              den += (x[idx] - xMean) * (x[idx] - xMean);
            }
            const slope = den !== 0 ? num / den : 0;
            const intercept = yMean - slope * xMean;
            sigma2 = Math.exp(intercept + slope * j);
          } else if (sigmas.length >= 1) {
            sigma2 = sigmas[sigmas.length - 1];
          } else {
            sigma2 = 0.0;
          }
        } else {
          throw new Error(`Método de extrapolação '${extrapolationMethod}' não suportado.`);
        }
      }

      sigmas.push(sigma2);
    }

    this.sigmaSquared = {
      values: sigmas,
      stdDevs: sigmas.map((s) => Math.sqrt(Math.max(0, s))),
      names: [...this.individualFactors.names],
    };
    return this.sigmaSquared;
  }

  calculateMackOriginMse() {
    if (!this.ibnrSummary) this.calculateIbnr();
    if (!this.projectedTriangle) this.projectTriangle();
    if (!this.sigmaSquared) this.calculateSigmaSquared();

    const f = this.individualFactors.values;
    const sig2 = this.sigmaSquared.values;

    // Pré-cálculo de S_k (soma das observações da coluna k usadas para calcular f_k)
    const S = new Array(this.nDevs - 1).fill(0);
    for (let k = 0; k < this.nDevs - 1; k++) {
      let sumCol = 0;
      for (let i = 0; i < this.nOrigins; i++) {
        const cCurr = this.triangleOriginal[i][k];
        const cNext = this.triangleOriginal[i][k + 1];
        if (cCurr !== null && cNext !== null && cCurr > 0) {
          sumCol += cCurr;
        }
      }
      S[k] = sumCol;
    }

    const records = [];
    for (let i = 0; i < this.nOrigins; i++) {
      const summaryItem = this.ibnrSummary[i];
      const lastDevIdx = summaryItem.lastDevIdx;
      const ultimate = summaryItem.ultimate;
      const ibnr = summaryItem.ibnr;

      if (lastDevIdx >= this.nDevs - 1) {
        records.push({
          originIndex: i,
          originYear: this.originYears[i],
          lastObserved: summaryItem.lastObserved,
          lastDevPeriod: summaryItem.lastDevPeriod,
          factorF: summaryItem.factorF,
          ultimate: ultimate,
          ibnr: ibnr,
          processVar: 0.0,
          parameterVar: 0.0,
          mse: 0.0,
          se: 0.0,
          cv: 0.0,
        });
      } else {
        let sumProc = 0.0;
        let sumParam = 0.0;

        for (let k = lastDevIdx; k < this.nDevs - 1; k++) {
          const C_ik = this.projectedTriangle[i][k];
          const termWeight = sig2[k] / (f[k] * f[k]);
          sumProc += termWeight / C_ik;
          sumParam += termWeight / S[k];
        }

        const procVar = ultimate * ultimate * sumProc;
        const paramVar = ultimate * ultimate * sumParam;
        const mse = procVar + paramVar;
        const se = Math.sqrt(Math.max(0, mse));
        const cv = ibnr > 0 ? (se / ibnr) * 100.0 : 0.0;

        records.push({
          originIndex: i,
          originYear: this.originYears[i],
          lastObserved: summaryItem.lastObserved,
          lastDevPeriod: summaryItem.lastDevPeriod,
          factorF: summaryItem.factorF,
          ultimate: ultimate,
          ibnr: ibnr,
          processVar: procVar,
          parameterVar: paramVar,
          mse: mse,
          se: se,
          cv: cv,
        });
      }
    }

    this.originMseSummary = records;
    return this.originMseSummary;
  }

  calculateMackCovarianceMatrix() {
    if (!this.originMseSummary) this.calculateMackOriginMse();

    const f = this.individualFactors.values;
    const sig2 = this.sigmaSquared.values;

    // Pré-cálculo de S_j
    const S = new Array(this.nDevs - 1).fill(0);
    for (let j = 0; j < this.nDevs - 1; j++) {
      let sumCol = 0;
      for (let i = 0; i < this.nOrigins; i++) {
        const cCurr = this.triangleOriginal[i][j];
        const cNext = this.triangleOriginal[i][j + 1];
        if (cCurr !== null && cNext !== null && cCurr > 0) {
          sumCol += cCurr;
        }
      }
      S[j] = sumCol;
    }

    const n = this.nOrigins;
    const cov = Array.from({ length: n }, () => new Array(n).fill(0));

    for (let i = 0; i < n; i++) {
      for (let k = 0; k < n; k++) {
        if (i === k) {
          cov[i][k] = this.originMseSummary[i].mse;
        } else {
          const lastI = this.ibnrSummary[i].lastDevIdx;
          const lastK = this.ibnrSummary[k].lastDevIdx;
          const jStart = Math.max(lastI, lastK);

          if (jStart >= this.nDevs - 1) {
            cov[i][k] = 0.0;
          } else {
            let sumCov = 0.0;
            for (let j = jStart; j < this.nDevs - 1; j++) {
              sumCov += sig2[j] / (f[j] * f[j] * S[j]);
            }
            const ultI = this.originMseSummary[i].ultimate;
            const ultK = this.originMseSummary[k].ultimate;
            cov[i][k] = ultI * ultK * sumCov;
          }
        }
      }
    }

    this.covarianceMatrix = cov;
    return this.covarianceMatrix;
  }

  calculateFullResults(extrapolationMethod = "mack", extrapolationValue = null) {
    this.calculateDevelopmentFactors();
    this.calculateCumulativeFactors();
    this.projectTriangle();
    this.calculateIbnr();
    this.calculateSigmaSquared(extrapolationMethod, extrapolationValue);
    this.calculateMackOriginMse();
    this.calculateMackCovarianceMatrix();

    // Consolidação de Totais
    let totalObserved = 0;
    let totalUltimate = 0;
    let totalIbnr = 0;
    let totalProcVar = 0;

    for (const rec of this.originMseSummary) {
      totalObserved += rec.lastObserved;
      totalUltimate += rec.ultimate;
      totalIbnr += rec.ibnr;
      totalProcVar += rec.processVar;
    }

    let totalMse = 0;
    for (let i = 0; i < this.nOrigins; i++) {
      for (let k = 0; k < this.nOrigins; k++) {
        totalMse += this.covarianceMatrix[i][k];
      }
    }

    const totalSe = Math.sqrt(Math.max(0, totalMse));
    const totalCv = totalIbnr > 0 ? (totalSe / totalIbnr) * 100.0 : 0.0;
    const totalParamVar = Math.max(0, totalMse - totalProcVar);
    const avgF = totalObserved > 0 ? totalUltimate / totalObserved : this.tailFactor;

    this.totals = {
      totalObserved,
      totalUltimate,
      totalIbnr,
      totalMse,
      totalSe,
      totalCv,
      totalProcVar,
      totalParamVar,
      procVarPct: totalMse > 0 ? (totalProcVar / totalMse) * 100.0 : 0.0,
      paramVarPct: totalMse > 0 ? (totalParamVar / totalMse) * 100.0 : 0.0,
      avgFactorF: avgF,
      ci95Lower: Math.max(0, totalIbnr - 1.96 * totalSe),
      ci95Upper: totalIbnr + 1.96 * totalSe,
    };

    return {
      triangleOriginal: this.triangleOriginal,
      originYears: this.originYears,
      devPeriods: this.devPeriods,
      individualFactors: this.individualFactors,
      cumulativeFactors: this.cumulativeFactors,
      projectedTriangle: this.projectedTriangle,
      sigmaSquared: this.sigmaSquared,
      originSummary: this.originMseSummary,
      covarianceMatrix: this.covarianceMatrix,
      totals: this.totals,
    };
  }
}

// Export para Node.js / CommonJS e compatibilidade com navegador
if (typeof module !== "undefined" && module.exports) {
  module.exports = MackChainLadderEngine;
}
