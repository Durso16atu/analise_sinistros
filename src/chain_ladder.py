"""
Módulo de Triangulação de Sinistros e Cálculo de IBNR via Método Chain Ladder.

Este módulo implementa a classe ChainLadder para processamento de triângulos de
desenvolvimento acumulados de sinistros, cálculo de fatores de desenvolvimento
individuais (link ratios) e acumulados (CDF), projeção do triângulo inferior,
estimativa dos sinistros finais (Ultimate) e apuração da provisão de IBNR
(Incurred But Not Reported).
"""

from typing import Union, Optional, List
import numpy as np
import pandas as pd


class ChainLadder:
    """
    Implementação clássica do método atuarial Chain Ladder (Link Ratio / Mack).

    Parâmetros:
    -----------
    triangle : Union[pd.DataFrame, np.ndarray, List[List[float]]]
        Triângulo de sinistros acumulados. Pode ser fornecido como DataFrame,
        matriz NumPy ou lista de listas. Células futuras não observadas
        devem ser preenchidas com np.nan ou None.
    origin_years : Optional[List[Union[int, str]]]
        Rótulos para os anos/períodos de ocorrência (linhas).
        Se None e triangle for DataFrame, usa triangle.index;
        caso contrário, gera índices numéricos sequenciais.
    dev_periods : Optional[List[Union[int, str]]]
        Rótulos para os períodos de desenvolvimento (colunas).
        Se None e triangle for DataFrame, usa triangle.columns;
        caso contrário, gera períodos 1, 2, ..., n.
    tail_factor : float, default=1.0
        Fator de cauda (tail factor) aplicado após o último período de
        desenvolvimento observado. O valor padrão é 1.0 (sem cauda adicional).
    """

    def __init__(
        self,
        triangle: Union[pd.DataFrame, np.ndarray, List[List[float]]],
        origin_years: Optional[List[Union[int, str]]] = None,
        dev_periods: Optional[List[Union[int, str]]] = None,
        tail_factor: float = 1.0,
    ) -> None:
        if tail_factor < 1.0:
            raise ValueError("O fator de cauda (tail_factor) deve ser >= 1.0.")
        self.tail_factor = float(tail_factor)

        # Padronização para pd.DataFrame com float
        self.triangle_original = self._prepare_dataframe(triangle, origin_years, dev_periods)
        self.n_origins, self.n_devs = self.triangle_original.shape

        # Atributos calculados sob demanda / armazenados em cache
        self._individual_factors: Optional[pd.Series] = None
        self._cumulative_factors: Optional[pd.Series] = None
        self._projected_triangle: Optional[pd.DataFrame] = None
        self._ibnr_summary: Optional[pd.DataFrame] = None
        self._sigma_squared: Optional[pd.Series] = None
        self._mack_origin_summary: Optional[pd.DataFrame] = None
        self._mack_covariance_matrix: Optional[pd.DataFrame] = None
        self._mack_summary: Optional[pd.DataFrame] = None

    def _prepare_dataframe(
        self,
        triangle: Union[pd.DataFrame, np.ndarray, List[List[float]]],
        origin_years: Optional[List[Union[int, str]]],
        dev_periods: Optional[List[Union[int, str]]],
    ) -> pd.DataFrame:
        """Converte e valida os dados de entrada em um DataFrame padrão."""
        if isinstance(triangle, pd.DataFrame):
            df = triangle.copy().astype(float)
            if origin_years is not None:
                df.index = origin_years
            if dev_periods is not None:
                df.columns = dev_periods
        elif isinstance(triangle, (np.ndarray, list)):
            arr = np.array(triangle, dtype=float)
            if arr.ndim != 2:
                raise ValueError("O triângulo de entrada deve ser bidimensional (2D).")
            rows, cols = arr.shape
            idx = origin_years if origin_years is not None else [f"Ano {i+1}" for i in range(rows)]
            col_names = dev_periods if dev_periods is not None else [f"Dev {j+1}" for j in range(cols)]
            df = pd.DataFrame(arr, index=idx, columns=col_names)
        else:
            raise TypeError("O triângulo deve ser um pd.DataFrame, np.ndarray ou List[List].")

        return df

    def calculate_development_factors(self, method: str = "volume_weighted") -> pd.Series:
        """
        Calcula os fatores de desenvolvimento individuais (f_j) entre períodos sucessivos.

        Por padrão, utiliza a média ponderada pelo volume de sinistros acumulados
        (estimador clássico de Mack):
            f_j = sum_{i=1}^{n-j} C_{i, j+1} / sum_{i=1}^{n-j} C_{i, j}

        Parâmetros:
        -----------
        method : str, default='volume_weighted'
            Método de cálculo. Atualmente suporta 'volume_weighted' (padrão atuarial)
            e 'simple_average' (média aritmética simples dos fatores individuais).

        Retorno:
        --------
        pd.Series : Fatores de desenvolvimento individuais f_j entre j e j+1.
        """
        cols = self.triangle_original.columns
        factors = []
        factor_names = []

        for j in range(self.n_devs - 1):
            col_curr = self.triangle_original.iloc[:, j]
            col_next = self.triangle_original.iloc[:, j + 1]

            # Considera apenas pares onde ambos os períodos foram observados
            valid_mask = col_curr.notna() & col_next.notna() & (col_curr > 0)
            valid_curr = col_curr[valid_mask]
            valid_next = col_next[valid_mask]

            if len(valid_curr) == 0:
                raise ValueError(
                    f"Não há dados pareados observados suficientes para o desenvolvimento "
                    f"entre '{cols[j]}' e '{cols[j+1]}'."
                )

            if method == "volume_weighted":
                f_j = valid_next.sum() / valid_curr.sum()
            elif method == "simple_average":
                f_j = (valid_next / valid_curr).mean()
            else:
                raise ValueError(f"Método '{method}' não suportado. Use 'volume_weighted' ou 'simple_average'.")

            factors.append(f_j)
            factor_names.append(f"{cols[j]} -> {cols[j+1]}")

        self._individual_factors = pd.Series(
            factors,
            index=factor_names,
            name="Individual_Development_Factor_f_j",
        )
        return self._individual_factors

    @property
    def individual_factors(self) -> pd.Series:
        """Retorna os fatores individuais f_j calculados."""
        if self._individual_factors is None:
            self.calculate_development_factors()
        return self._individual_factors

    def calculate_cumulative_factors(self) -> pd.Series:
        """
        Calcula os fatores acumulados de desenvolvimento (Cumulative Development Factors - CDF)
        ou fatores acumulados de cauda (F_j), projetando de cada estágio j até o custo final (Ultimate).

        F_j = (prod_{k=j}^{n-1} f_k) * tail_factor
        Para o estágio final n: F_n = tail_factor

        Retorno:
        --------
        pd.Series : Fatores acumulados F_j para cada coluna de desenvolvimento.
        """
        f = self.individual_factors.values
        cols = self.triangle_original.columns
        cdf_values = np.zeros(self.n_devs, dtype=float)

        # Último período recebe o tail_factor
        cdf_values[-1] = self.tail_factor

        # Produto acumulado reverso da cauda até o período 1
        for j in range(self.n_devs - 2, -1, -1):
            cdf_values[j] = cdf_values[j + 1] * f[j]

        self._cumulative_factors = pd.Series(
            cdf_values,
            index=cols,
            name="Cumulative_Development_Factor_F_j",
        )
        return self._cumulative_factors

    @property
    def cumulative_factors(self) -> pd.Series:
        """Retorna os fatores acumulados F_j calculados."""
        if self._cumulative_factors is None:
            self.calculate_cumulative_factors()
        return self._cumulative_factors

    def project_triangle(self) -> pd.DataFrame:
        """
        Projeta o triângulo inferior completo utilizando os fatores individuais f_j.

        Para cada célula não observada C_{i, j+1}, aplica:
            C_{i, j+1} = C_{i, j} * f_j

        Retorno:
        --------
        pd.DataFrame : Triângulo completo com valores históricos e projeções futuras.
        """
        f = self.individual_factors.values
        projected = self.triangle_original.copy()

        for i in range(self.n_origins):
            for j in range(1, self.n_devs):
                if pd.isna(projected.iloc[i, j]):
                    prev_val = projected.iloc[i, j - 1]
                    if not pd.isna(prev_val):
                        projected.iloc[i, j] = prev_val * f[j - 1]

        self._projected_triangle = projected
        return self._projected_triangle

    @property
    def projected_triangle(self) -> pd.DataFrame:
        """Retorna o triângulo com projeções completas."""
        if self._projected_triangle is None:
            self.project_triangle()
        return self._projected_triangle

    def calculate_ibnr(self) -> pd.DataFrame:
        """
        Estima os sinistros finais (Ultimate) e calcula a provisão de IBNR para cada ano de origem.

        Para cada ano de ocorrência i:
        1. Identifica o último sinistro acumulado observado C_{i, j_obs} e o período j_obs.
        2. Obtém o fator acumulado F_{j_obs}.
        3. Sinistro Final (Ultimate) = C_{i, j_obs} * F_{j_obs}
        4. IBNR_i = Ultimate_i - C_{i, j_obs}

        Retorno:
        --------
        pd.DataFrame : Tabela detalhada por ano de ocorrência contendo Último Observado,
                       Estágio Atual, Fator CDF, Sinistro Final Estimado e IBNR.
        """
        cdf = self.cumulative_factors
        cols = self.triangle_original.columns

        records = []
        for i, origin in enumerate(self.triangle_original.index):
            row = self.triangle_original.iloc[i]
            # Último valor válido observado na linha
            valid_series = row.dropna()
            if valid_series.empty:
                latest_val = 0.0
                latest_col = cols[0]
            else:
                latest_val = valid_series.iloc[-1]
                latest_col = valid_series.index[-1]

            factor_F = cdf[latest_col]
            ultimate = latest_val * factor_F
            ibnr = ultimate - latest_val

            records.append({
                "Ano_Ocorrencia": origin,
                "Ultimo_Sinistro_Obs": latest_val,
                "Ultimo_Periodo_Dev": latest_col,
                "Fator_CDF_Fj": factor_F,
                "Sinistro_Final_Ultimate": ultimate,
                "Provisao_IBNR": ibnr,
            })

        df_summary = pd.DataFrame(records).set_index("Ano_Ocorrencia")
        self._ibnr_summary = df_summary
        return self._ibnr_summary

    @property
    def ibnr_summary(self) -> pd.DataFrame:
        """Retorna a tabela de resumo de IBNR por ano de ocorrência."""
        if self._ibnr_summary is None:
            self.calculate_ibnr()
        return self._ibnr_summary

    @property
    def total_ibnr(self) -> float:
        """Retorna o valor total da provisão de IBNR consolidada."""
        return float(self.ibnr_summary["Provisao_IBNR"].sum())

    @property
    def total_ultimate(self) -> float:
        """Retorna o valor total dos sinistros finais projetados."""
        return float(self.ibnr_summary["Sinistro_Final_Ultimate"].sum())

    @property
    def total_observed(self) -> float:
        """Retorna o montante total de sinistros acumulados observados na diagonal mais recente."""
        return float(self.ibnr_summary["Ultimo_Sinistro_Obs"].sum())

    # ==========================================================================
    # MODELAGEM ESTOCÁSTICA - MÉTODO DE THOMAS MACK (1993)
    # ==========================================================================

    def calculate_sigma_squared(
        self,
        extrapolation_method: str = "mack",
        extrapolation_value: Optional[float] = None,
    ) -> pd.Series:
        """
        Calcula os estimadores de variância residual sigma_j^2 para cada coluna de desenvolvimento,
        conforme o modelo estocástico de Thomas Mack (1993).

        Para colunas com graus de liberdade suficientes (m_j - 1 > 0):
            sigma_j^2 = (1 / (m_j - 1)) * sum_{i} C_{i, j} * ((C_{i, j+1} / C_{i, j}) - f_j)^2
        onde m_j é o número de pares observados no período de transição j -> j+1.

        Para a última coluna de transição (j = n-2 em índice 0, ou seja, j = n-1 em notação 1-indexada),
        onde m_j = 1 e graus de liberdade = 0:
        - Se extrapolation_value for informado, utiliza esse valor numérico.
        - Se extrapolation_method == "mack":
            * Se f_j == 1.0: sigma_j^2 = 0.0
            * Se existirem pelo menos 2 sigmas anteriores válidos (sigma_{j-2}^2 e sigma_{j-1}^2):
              sigma_j^2 = min(sigma_{j-1}^4 / sigma_{j-2}^2, min(sigma_{j-2}^2, sigma_{j-1}^2))
            * Se houver apenas 1 anterior: sigma_j^2 = sigma_{j-1}^2
            * Se nenhum: sigma_j^2 = 0.0
        - Se extrapolation_method == "min":
            * min dos 2 anteriores (ou o anterior caso exista apenas 1).
        - Se extrapolation_method == "log_linear":
            * Ajusta regressão linear ln(sigma_k^2) = a + b*k sobre os valores válidos e extrapola.

        Retorno:
        --------
        pd.Series : Estimadores sigma_j^2 para cada período de transição.
        """
        factors = self.individual_factors.values
        sigmas = []
        transition_names = list(self.individual_factors.index)

        for j in range(self.n_devs - 1):
            col_curr = self.triangle_original.iloc[:, j]
            col_next = self.triangle_original.iloc[:, j + 1]

            valid_mask = col_curr.notna() & col_next.notna() & (col_curr > 0)
            valid_curr = col_curr[valid_mask]
            valid_next = col_next[valid_mask]

            m_j = len(valid_curr)
            f_j = factors[j]

            if m_j > 1:
                residuals = (valid_next / valid_curr) - f_j
                sigma2 = float(((valid_curr * (residuals ** 2)).sum()) / (m_j - 1))
            else:
                # Tratamento de extrapolação para m_j <= 1 (típico para j = n - 2)
                if extrapolation_value is not None:
                    sigma2 = float(extrapolation_value)
                elif extrapolation_method == "mack":
                    if np.isclose(f_j, 1.0):
                        sigma2 = 0.0
                    elif len(sigmas) >= 2 and sigmas[-2] > 0:
                        s_prev2 = sigmas[-2]
                        s_prev1 = sigmas[-1]
                        ratio = (s_prev1 ** 2) / s_prev2
                        sigma2 = float(min(ratio, min(s_prev2, s_prev1)))
                    elif len(sigmas) >= 1:
                        sigma2 = float(sigmas[-1])
                    else:
                        sigma2 = 0.0
                elif extrapolation_method == "min":
                    if len(sigmas) >= 2:
                        sigma2 = float(min(sigmas[-1], sigmas[-2]))
                    elif len(sigmas) >= 1:
                        sigma2 = float(sigmas[-1])
                    else:
                        sigma2 = 0.0
                elif extrapolation_method == "log_linear":
                    valid_idx = [k for k, s in enumerate(sigmas) if s > 0]
                    if len(valid_idx) >= 2:
                        y = [np.log(sigmas[k]) for k in valid_idx]
                        poly = np.polyfit(valid_idx, y, deg=1)
                        sigma2 = float(np.exp(poly[1] + poly[0] * j))
                    elif len(sigmas) >= 1:
                        sigma2 = float(sigmas[-1])
                    else:
                        sigma2 = 0.0
                else:
                    raise ValueError(f"Método de extrapolação '{extrapolation_method}' não suportado.")

            sigmas.append(sigma2)

        self._sigma_squared = pd.Series(
            sigmas,
            index=transition_names,
            name="Mack_Residual_Variance_sigma_j2",
        )
        return self._sigma_squared

    @property
    def sigma_squared(self) -> pd.Series:
        """Retorna os estimadores de variância residual sigma_j^2 de Mack."""
        if self._sigma_squared is None:
            self.calculate_sigma_squared()
        return self._sigma_squared

    @property
    def sigma(self) -> pd.Series:
        """Retorna o desvio padrão residual sigma_j de Mack."""
        return np.sqrt(self.sigma_squared).rename("Mack_Residual_Std_sigma_j")

    def calculate_mack_origin_mse(self) -> pd.DataFrame:
        """
        Calcula o erro médio quadrático de predição (m.s.e.), erro padrão (s.e.)
        e coeficiente de variação (CV) individual para cada safra (ano de ocorrência),
        decompondo entre risco de processo e risco de parâmetro conforme Thomas Mack (1993, Teorema 1).

        Fórmula de Mack (1993, fórmula 8):
            m.s.e.(C_{i, n}) = (C_{i, n})^2 * sum_{k=I_i}^{n-1} (sigma_k^2 / f_k^2) * [ (1 / C_{i, k}) + (1 / S_k) ]
        onde:
            - C_{i, k} é o sinistro acumulado estimado no estágio k (termo de Risco de Processo: 1 / C_{i, k}).
            - S_k = sum_{m=1}^{n-k} C_{m, k} é a soma dos sinistros observados na coluna k (termo de Risco de Parâmetro: 1 / S_k).

        Retorno:
        --------
        pd.DataFrame : Tabela detalhada por safra com Sinistro Final, IBNR, Risco de Processo,
                       Risco de Parâmetro, MSE, Erro Padrão (s.e.) e CV (%).
        """
        f = self.individual_factors.values
        sig2 = self.sigma_squared.values
        cols = self.triangle_original.columns
        origins = self.triangle_original.index

        # Pré-cálculo de S_k (soma das observações pareadas da coluna k)
        S = np.zeros(self.n_devs - 1, dtype=float)
        for k in range(self.n_devs - 1):
            col_curr = self.triangle_original.iloc[:, k]
            col_next = self.triangle_original.iloc[:, k + 1]
            valid_mask = col_curr.notna() & col_next.notna() & (col_curr > 0)
            S[k] = float(col_curr[valid_mask].sum())

        records = []
        for i, origin in enumerate(origins):
            row = self.triangle_original.iloc[i]
            valid_series = row.dropna()

            if valid_series.empty:
                I_i = 0
                latest_val = 0.0
                latest_col = cols[0]
            else:
                latest_col = valid_series.index[-1]
                I_i = cols.get_loc(latest_col)
                latest_val = float(valid_series.iloc[-1])

            factor_F = float(self.cumulative_factors[latest_col])
            ultimate = float(latest_val * factor_F)
            ibnr = float(ultimate - latest_val)

            # Se a safra já atingiu o desenvolvimento final observado
            if I_i >= self.n_devs - 1:
                proc_var = 0.0
                param_var = 0.0
                mse = 0.0
                se = 0.0
                cv = 0.0
            else:
                sum_proc = 0.0
                sum_param = 0.0
                for k in range(I_i, self.n_devs - 1):
                    # C_{i, k}: valor observado (em k == I_i) ou projetado (em k > I_i)
                    C_ik = float(self.projected_triangle.iloc[i, k])
                    term_weight = sig2[k] / (f[k] ** 2)
                    sum_proc += term_weight / C_ik
                    sum_param += term_weight / S[k]

                proc_var = float((ultimate ** 2) * sum_proc)
                param_var = float((ultimate ** 2) * sum_param)
                mse = float(proc_var + param_var)
                se = float(np.sqrt(mse))
                cv = float((se / ibnr) * 100.0) if ibnr > 0 else 0.0

            records.append({
                "Safra": origin,
                "Sinistro_Acumulado_Obs": latest_val,
                "Ultimo_Periodo_Dev": latest_col,
                "Fator_Fj": factor_F,
                "Sinistro_Final_Ultimate": ultimate,
                "Provisao_IBNR": ibnr,
                "Risco_Processo_Var": proc_var,
                "Risco_Parametro_Var": param_var,
                "MSE": mse,
                "Erro_Padrao_se": se,
                "CV_pct": cv,
            })

        df = pd.DataFrame(records).set_index("Safra")
        self._mack_origin_summary = df
        return self._mack_origin_summary

    @property
    def mack_origin_summary(self) -> pd.DataFrame:
        """Retorna o quadro de erros padrões e decomposição de variância por safra de Mack."""
        if self._mack_origin_summary is None:
            self.calculate_mack_origin_mse()
        return self._mack_origin_summary

    def calculate_mack_covariance_matrix(self) -> pd.DataFrame:
        """
        Calcula a matriz de covariância entre as provisões de IBNR e sinistros finais
        das diferentes safras, conforme Thomas Mack (1993, Teorema 2):

        Para i != k (safras distintas):
            Cov(C_{i, n}, C_{k, n}) = C_{i, n} * C_{k, n} * sum_{j = max(I_i, I_k)}^{n-1} (sigma_j^2 / (f_j^2 * S_j))
        Para i == k:
            Cov(C_{i, n}, C_{i, n}) = m.s.e.(C_{i, n})

        Retorno:
        --------
        pd.DataFrame : Matriz quadrada de covariância (n_origins x n_origins).
        """
        f = self.individual_factors.values
        sig2 = self.sigma_squared.values
        cols = self.triangle_original.columns
        origins = self.triangle_original.index
        n_origins = len(origins)

        # Pré-cálculo de S_j
        S = np.zeros(self.n_devs - 1, dtype=float)
        for j in range(self.n_devs - 1):
            col_curr = self.triangle_original.iloc[:, j]
            col_next = self.triangle_original.iloc[:, j + 1]
            valid_mask = col_curr.notna() & col_next.notna() & (col_curr > 0)
            S[j] = float(col_curr[valid_mask].sum())

        # Índices de última observação e Ultimates por safra
        last_obs_idx = np.zeros(n_origins, dtype=int)
        ultimates = np.zeros(n_origins, dtype=float)
        mses = self.mack_origin_summary["MSE"].values

        for i in range(n_origins):
            valid_series = self.triangle_original.iloc[i].dropna()
            if valid_series.empty:
                last_obs_idx[i] = 0
            else:
                last_col = valid_series.index[-1]
                last_obs_idx[i] = cols.get_loc(last_col)
            ultimates[i] = self.mack_origin_summary.iloc[i]["Sinistro_Final_Ultimate"]

        cov_matrix = np.zeros((n_origins, n_origins), dtype=float)

        for i in range(n_origins):
            for k in range(n_origins):
                if i == k:
                    cov_matrix[i, k] = mses[i]
                else:
                    j_start = max(last_obs_idx[i], last_obs_idx[k])
                    if j_start >= self.n_devs - 1:
                        cov_matrix[i, k] = 0.0
                    else:
                        sum_cov = 0.0
                        for j in range(j_start, self.n_devs - 1):
                            sum_cov += sig2[j] / ((f[j] ** 2) * S[j])
                        cov_matrix[i, k] = float(ultimates[i] * ultimates[k] * sum_cov)

        df_cov = pd.DataFrame(cov_matrix, index=origins, columns=origins)
        self._mack_covariance_matrix = df_cov
        return self._mack_covariance_matrix

    @property
    def mack_covariance_matrix(self) -> pd.DataFrame:
        """Retorna a matriz de covariância entre safras de Mack."""
        if self._mack_covariance_matrix is None:
            self.calculate_mack_covariance_matrix()
        return self._mack_covariance_matrix

    @property
    def total_mack_mse(self) -> float:
        """
        Retorna o erro médio quadrático de predição total consolidado da provisão (Mack, 1993):
        m.s.e.(R_total) = sum_{i} m.s.e.(R_i) + 2 * sum_{i < k} Cov(R_i, R_k)
        """
        return float(self.mack_covariance_matrix.values.sum())

    @property
    def total_mack_se(self) -> float:
        """Retorna o erro padrão total da provisão agregada de IBNR: s.e.(R_total)."""
        return float(np.sqrt(self.total_mack_mse))

    @property
    def total_mack_cv(self) -> float:
        """Retorna o coeficiente de variação total da provisão agregada de IBNR (em fração decimal)."""
        return float(self.total_mack_se / self.total_ibnr) if self.total_ibnr > 0 else 0.0

    @property
    def total_mack_process_variance(self) -> float:
        """Retorna o risco de processo agregado total (soma das variâncias de processo individuais)."""
        return float(self.mack_origin_summary["Risco_Processo_Var"].sum())

    @property
    def total_mack_parameter_variance(self) -> float:
        """
        Retorna o risco de parâmetro agregado total (incluindo todas as covariâncias entre safras):
        Var_param(R_total) = m.s.e.(R_total) - Var_proc(R_total).
        """
        return float(self.total_mack_mse - self.total_mack_process_variance)

    def summary_mack(self, include_total: bool = True) -> pd.DataFrame:
        """
        Gera uma tabela completa consolidando estimativas pontuais e métricas estocásticas de Mack:
        Safra, Sinistro Acumulado Observado, Fator F_j, Sinistro Final Projetado,
        Provisão IBNR, Erro Padrão (s.e.) e CV (%).

        Parâmetros:
        -----------
        include_total : bool, default=True
            Se True, inclui linha ao final com os totais da carteira e o s.e. total com covariâncias.

        Retorno:
        --------
        pd.DataFrame : Tabela consolidada com as colunas especificadas.
        """
        origin_df = self.mack_origin_summary

        rows = []
        for origin in origin_df.index:
            row = origin_df.loc[origin]
            rows.append({
                "Safra": origin,
                "Sinistro Acumulado Observado": row["Sinistro_Acumulado_Obs"],
                "Fator F_j": row["Fator_Fj"],
                "Sinistro Final Projetado": row["Sinistro_Final_Ultimate"],
                "Provisão IBNR": row["Provisao_IBNR"],
                "Erro Padrão (s.e.)": row["Erro_Padrao_se"],
                "CV (%)": row["CV_pct"],
            })

        if include_total:
            total_obs = self.total_observed
            total_ult = self.total_ultimate
            total_ibnr = self.total_ibnr
            total_se = self.total_mack_se
            total_cv_pct = self.total_mack_cv * 100.0
            avg_F = (total_ult / total_obs) if total_obs > 0 else self.tail_factor

            rows.append({
                "Safra": "Total",
                "Sinistro Acumulado Observado": total_obs,
                "Fator F_j": avg_F,
                "Sinistro Final Projetado": total_ult,
                "Provisão IBNR": total_ibnr,
                "Erro Padrão (s.e.)": total_se,
                "CV (%)": total_cv_pct,
            })

        df_result = pd.DataFrame(rows).set_index("Safra", drop=False)
        self._mack_summary = df_result
        return df_result

    def format_results(self) -> str:
        """Gera um relatório textual detalhado e formatado dos resultados determinísticos e estocásticos."""
        sep = "=" * 80
        sub_sep = "-" * 80

        lines = [
            sep,
            "                   RELATÓRIO ATUARIAL - MÉTODO CHAIN LADDER & MACK",
            sep,
            "",
            "1. TRIÂNGULO DE DESENVOLVIMENTO ACUMULADO ORIGINAL:",
            sub_sep,
            self.triangle_original.map(lambda x: f"{x:12,.2f}" if pd.notna(x) else f"{'-':>12}").to_string(),
            "",
            "2. FATORES DE DESENVOLVIMENTO INDIVIDUAIS (f_j):",
            sub_sep,
        ]

        f_df = pd.DataFrame({
            "Período de Transição": self.individual_factors.index,
            "Fator f_j": self.individual_factors.values,
        })
        lines.append(f_df.to_string(index=False, formatters={"Fator f_j": "{:,.4f}".format}))

        lines.extend([
            "",
            f"3. FATORES ACUMULADOS ATÉ O ULTIMATE (CDF - F_j) [Fator Cauda = {self.tail_factor:.4f}]:",
            sub_sep,
        ])
        cdf_df = pd.DataFrame({
            "Período de Desenvolvimento": self.cumulative_factors.index,
            "Fator Acumulado F_j": self.cumulative_factors.values,
        })
        lines.append(cdf_df.to_string(index=False, formatters={"Fator Acumulado F_j": "{:,.4f}".format}))

        lines.extend([
            "",
            "4. TRIÂNGULO PROJETADO COMPLETO (COM TRIÂNGULO INFERIOR PREENCHIDO):",
            sub_sep,
            self.projected_triangle.map(lambda x: f"{x:12,.2f}").to_string(),
            "",
            "5. QUADRO DE ESTIMATIVAS DE SINISTROS FINAIS E PROVISÃO DE IBNR:",
            sub_sep,
        ])

        formatted_summary = self.ibnr_summary.copy()
        formatted_summary["Ultimo_Sinistro_Obs"] = formatted_summary["Ultimo_Sinistro_Obs"].map("{:,.2f}".format)
        formatted_summary["Fator_CDF_Fj"] = formatted_summary["Fator_CDF_Fj"].map("{:,.4f}".format)
        formatted_summary["Sinistro_Final_Ultimate"] = formatted_summary["Sinistro_Final_Ultimate"].map("{:,.2f}".format)
        formatted_summary["Provisao_IBNR"] = formatted_summary["Provisao_IBNR"].map("{:,.2f}".format)
        lines.append(formatted_summary.to_string())

        lines.extend([
            "",
            "6. TOTAIS CONSOLIDADOS DETERMINÍSTICOS DA CARTEIRA:",
            sub_sep,
            f"   Total de Sinistros Observados (Última Posição): R$ {self.total_observed:15,.2f}",
            f"   Total de Sinistros Finais Estimados (Ultimate): R$ {self.total_ultimate:15,.2f}",
            f"   PROVISÃO TOTAL DE IBNR REQUERIDA             : R$ {self.total_ibnr:15,.2f}",
            "",
            "7. MODELAGEM ESTOCÁSTICA DE THOMAS MACK (1993):",
            sub_sep,
            "7.1 Desvios Padrão Residuais por Coluna de Desenvolvimento (sigma_j):",
        ])

        sig_df = pd.DataFrame({
            "Período de Transição": self.sigma_squared.index,
            "Fator f_j": self.individual_factors.values,
            "sigma_j^2": self.sigma_squared.values,
            "sigma_j": self.sigma.values,
        })
        lines.append(sig_df.to_string(index=False, formatters={
            "Fator f_j": "{:,.4f}".format,
            "sigma_j^2": "{:,.4f}".format,
            "sigma_j": "{:,.4f}".format,
        }))

        lines.extend([
            "",
            "7.2 Quadro Resumo de Reservas e Erros Padrão de Mack:",
            sub_sep,
        ])

        mack_table = self.summary_mack(include_total=True).copy()
        mack_formatted = pd.DataFrame({
            "Safra": mack_table["Safra"],
            "Sinistro Acumulado Obs": mack_table["Sinistro Acumulado Observado"].map("{:,.2f}".format),
            "Fator F_j": mack_table["Fator F_j"].map("{:,.4f}".format),
            "Sinistro Final Projetado": mack_table["Sinistro Final Projetado"].map("{:,.2f}".format),
            "Provisão IBNR": mack_table["Provisão IBNR"].map("{:,.2f}".format),
            "Erro Padrão (s.e.)": mack_table["Erro Padrão (s.e.)"].map("{:,.2f}".format),
            "CV (%)": mack_table["CV (%)"].map("{:,.2f}%".format),
        }).set_index("Safra")
        lines.append(mack_formatted.to_string())

        proc_pct = (self.total_mack_process_variance / self.total_mack_mse) * 100.0 if self.total_mack_mse > 0 else 0.0
        param_pct = (self.total_mack_parameter_variance / self.total_mack_mse) * 100.0 if self.total_mack_mse > 0 else 0.0
        ci_lower = max(0.0, self.total_ibnr - 1.96 * self.total_mack_se)
        ci_upper = self.total_ibnr + 1.96 * self.total_mack_se

        lines.extend([
            "",
            "7.3 Decomposição da Incerteza e Intervalo de Confiança (Mack):",
            sub_sep,
            f"   Risco de Processo Total (Variância)       : R$ {self.total_mack_process_variance:15,.2f} ({proc_pct:5.1f}%)",
            f"   Risco de Parâmetro Total (com Covariâncias): R$ {self.total_mack_parameter_variance:15,.2f} ({param_pct:5.1f}%)",
            f"   MSE Total Consolidado m.s.e.(R_total)     : R$ {self.total_mack_mse:15,.2f}",
            f"   ERRO PADRÃO TOTAL CONSOLIDADO s.e.(R_total): R$ {self.total_mack_se:15,.2f}",
            f"   COEFICIENTE DE VARIAÇÃO TOTAL (CV)        : {self.total_mack_cv * 100.0:14.2f}%",
            f"   Intervalo de Confiança 95% Aprox. (Normal): [R$ {ci_lower:,.2f} ; R$ {ci_upper:,.2f}]",
            sep,
        ])

        return "\n".join(lines)


# ==============================================================================
# EXEMPLO DIDÁTICO AUTOEXECUTÁVEL
# ==============================================================================
if __name__ == "__main__":
    # Simulação de um triângulo de desenvolvimento de sinistros acumulados (R$ mil)
    # 5 anos de ocorrência (2020 a 2024) com até 5 anos de desenvolvimento
    anos_ocorrencia = [2020, 2021, 2022, 2023, 2024]
    periodos_desenvolvimento = ["Ano 1", "Ano 2", "Ano 3", "Ano 4", "Ano 5"]

    dados_sinistros = [
        [1000.0, 1450.0, 1740.0, 1914.0, 2010.0],  # 2020: Totalmente desenvolvido
        [1150.0, 1690.0, 2030.0, 2235.0,  np.nan],  # 2021: Faltando 1 ano de maturação
        [1220.0, 1805.0, 2185.0,  np.nan,  np.nan],  # 2022: Faltando 2 anos de maturação
        [1350.0, 1990.0,  np.nan,  np.nan,  np.nan],  # 2023: Faltando 3 anos de maturação
        [1480.0,  np.nan,  np.nan,  np.nan,  np.nan],  # 2024: Apenas 1 ano observado
    ]

    triangulo_df = pd.DataFrame(
        dados_sinistros,
        index=anos_ocorrencia,
        columns=periodos_desenvolvimento,
    )

    print("\nExecutando triangulação via Chain Ladder & Mack (1993) [Tail Factor = 1.0]...\n")

    modelo = ChainLadder(
        triangle=triangulo_df,
        tail_factor=1.0,
    )

    # Exibe o relatório formatado completo
    print(modelo.format_results())

