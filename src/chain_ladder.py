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

    def format_results(self) -> str:
        """Gera um relatório textual detalhado e formatado dos resultados."""
        sep = "=" * 80
        sub_sep = "-" * 80

        lines = [
            sep,
            "                   RELATÓRIO ATUARIAL - MÉTODO CHAIN LADDER",
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
            "6. TOTAIS CONSOLIDADOS DA CARTEIRA:",
            sub_sep,
            f"   Total de Sinistros Observados (Última Posição): R$ {self.total_observed:15,.2f}",
            f"   Total de Sinistros Finais Estimados (Ultimate): R$ {self.total_ultimate:15,.2f}",
            f"   PROVISÃO TOTAL DE IBNR REQUERIDA             : R$ {self.total_ibnr:15,.2f}",
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

    print("\nExecutando triangulação via Chain Ladder com cauda de 1.02 (2% adicional na cauda)...\n")

    # Instanciando o modelo com tail factor prudencial de 1.02
    modelo = ChainLadder(
        triangle=triangulo_df,
        tail_factor=1.02,
    )

    # Exibe o relatório formatado completo
    print(modelo.format_results())
