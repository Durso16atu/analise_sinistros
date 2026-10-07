import unittest
import numpy as np
import pandas as pd
from src.chain_ladder import ChainLadder


class TestChainLadder(unittest.TestCase):
    def setUp(self):
        # Triângulo clássico 3x3 para conferência analítica exata
        # Dev 1: [1000, 1200, 1400]
        # Dev 2: [1500, 1860, NaN]
        # Dev 3: [1800, NaN,  NaN]
        self.dados = [
            [1000.0, 1500.0, 1800.0],
            [1200.0, 1860.0,  np.nan],
            [1400.0,  np.nan,  np.nan],
        ]
        self.anos = [2022, 2023, 2024]
        self.periodos = ["Dev 1", "Dev 2", "Dev 3"]

    def test_fatores_individuais_e_acumulados(self):
        modelo = ChainLadder(self.dados, origin_years=self.anos, dev_periods=self.periodos, tail_factor=1.0)
        f_j = modelo.individual_factors

        # f1 = (1500 + 1860) / (1000 + 1200) = 3360 / 2200 = 1.527272...
        self.assertAlmostEqual(f_j.iloc[0], 3360.0 / 2200.0, places=4)
        # f2 = 1800 / 1500 = 1.2
        self.assertAlmostEqual(f_j.iloc[1], 1.2, places=4)

        # Fatores acumulados F_j (CDF)
        F_j = modelo.cumulative_factors
        # F3 = 1.0 (tail=1.0)
        self.assertAlmostEqual(F_j.iloc[2], 1.0, places=4)
        # F2 = 1.2 * 1.0 = 1.2
        self.assertAlmostEqual(F_j.iloc[1], 1.2, places=4)
        # F1 = 1.527272... * 1.2 = 1.832727...
        self.assertAlmostEqual(F_j.iloc[0], (3360.0 / 2200.0) * 1.2, places=4)

    def test_calculo_ibnr_e_ultimate(self):
        modelo = ChainLadder(self.dados, origin_years=self.anos, dev_periods=self.periodos, tail_factor=1.0)
        ibnr_df = modelo.ibnr_summary

        # 2022: Último obs = 1800, Ultimate = 1800, IBNR = 0
        self.assertAlmostEqual(ibnr_df.loc[2022, "Sinistro_Final_Ultimate"], 1800.0, places=2)
        self.assertAlmostEqual(ibnr_df.loc[2022, "Provisao_IBNR"], 0.0, places=2)

        # 2023: Último obs = 1860, F2 = 1.2, Ultimate = 2232, IBNR = 372
        self.assertAlmostEqual(ibnr_df.loc[2023, "Sinistro_Final_Ultimate"], 2232.0, places=2)
        self.assertAlmostEqual(ibnr_df.loc[2023, "Provisao_IBNR"], 372.0, places=2)

        # 2024: Último obs = 1400, F1 = 1.832727..., Ultimate = 2565.818..., IBNR = 1165.818...
        esperado_ult_2024 = 1400.0 * ((3360.0 / 2200.0) * 1.2)
        self.assertAlmostEqual(ibnr_df.loc[2024, "Sinistro_Final_Ultimate"], esperado_ult_2024, places=2)
        self.assertAlmostEqual(ibnr_df.loc[2024, "Provisao_IBNR"], esperado_ult_2024 - 1400.0, places=2)

        # Total IBNR
        total_esperado = 0.0 + 372.0 + (esperado_ult_2024 - 1400.0)
        self.assertAlmostEqual(modelo.total_ibnr, total_esperado, places=2)

    def test_entrada_dataframe_e_cauda(self):
        df = pd.DataFrame(self.dados, index=self.anos, columns=self.periodos)
        modelo = ChainLadder(df, tail_factor=1.05)
        # F3 deve ser igual ao tail_factor
        self.assertAlmostEqual(modelo.cumulative_factors.iloc[2], 1.05, places=4)
        # Triângulo projetado não deve conter NaNs
        self.assertFalse(modelo.projected_triangle.isna().any().any())

    def test_mack_sigma_squared_e_extrapolacao(self):
        modelo = ChainLadder(self.dados, origin_years=self.anos, dev_periods=self.periodos, tail_factor=1.0)
        sig2 = modelo.sigma_squared

        # Para j=0 (Dev 1 -> Dev 2): sigma_0^2 = 15/11 exato
        # Termo 1: 1000 * (1.5 - 3360/2200)^2 = 90/121
        # Termo 2: 1200 * (1.55 - 3360/2200)^2 = 75/121
        # Soma = 165/121 = 15/11 ~= 1.363636...
        self.assertAlmostEqual(sig2.iloc[0], 15.0 / 11.0, places=5)

        # Para j=1 (Dev 2 -> Dev 3): extrapolação Mack para n=3 (herda sigma_0^2)
        self.assertAlmostEqual(sig2.iloc[1], 15.0 / 11.0, places=5)

        # Desvio padrão residual sigma_j = sqrt(sigma_j^2)
        self.assertAlmostEqual(modelo.sigma.iloc[0], np.sqrt(15.0 / 11.0), places=5)

        # Teste com valor manual de extrapolação
        sig2_manual = modelo.calculate_sigma_squared(extrapolation_value=2.5)
        self.assertAlmostEqual(sig2_manual.iloc[1], 2.5, places=5)

    def test_mack_erros_padrao_individuais_e_decomposicao(self):
        modelo = ChainLadder(self.dados, origin_years=self.anos, dev_periods=self.periodos, tail_factor=1.0)
        df_mack = modelo.mack_origin_summary

        # 2022: Totalmente desenvolvido -> MSE = 0, s.e. = 0, CV = 0
        self.assertEqual(df_mack.loc[2022, "MSE"], 0.0)
        self.assertEqual(df_mack.loc[2022, "Erro_Padrao_se"], 0.0)
        self.assertEqual(df_mack.loc[2022, "CV_pct"], 0.0)

        # 2023:
        # C_{2,3} = 2232.0, IBNR = 372.0
        # MSE_2 = (62496 / 11) ~= 5681.4545...
        # Risco de processo: (15/11) * 1860 = 27900 / 11 ~= 2536.3636...
        # Risco de parâmetro: (15/11) * 2306.4 = 34596 / 11 ~= 3145.0909...
        mse_2_esperado = 62496.0 / 11.0
        se_2_esperado = np.sqrt(mse_2_esperado)
        cv_2_esperado = (se_2_esperado / 372.0) * 100.0

        self.assertAlmostEqual(df_mack.loc[2023, "Risco_Processo_Var"], 27900.0 / 11.0, places=4)
        self.assertAlmostEqual(df_mack.loc[2023, "Risco_Parametro_Var"], 34596.0 / 11.0, places=4)
        self.assertAlmostEqual(df_mack.loc[2023, "MSE"], mse_2_esperado, places=4)
        self.assertAlmostEqual(df_mack.loc[2023, "Erro_Padrao_se"], se_2_esperado, places=4)
        self.assertAlmostEqual(df_mack.loc[2023, "CV_pct"], cv_2_esperado, places=4)

        # 2024:
        # Ultimate = 28224 / 11 ~= 2565.818...
        # MSE analítico verificado numericamente ~= 11570.4162...
        se_3_esperado = np.sqrt(df_mack.loc[2024, "MSE"])
        self.assertAlmostEqual(df_mack.loc[2024, "Erro_Padrao_se"], se_3_esperado, places=4)
        self.assertTrue(df_mack.loc[2024, "MSE"] > df_mack.loc[2023, "MSE"])

    def test_mack_covariancia_e_erro_padrao_total(self):
        modelo = ChainLadder(self.dados, origin_years=self.anos, dev_periods=self.periodos, tail_factor=1.0)
        cov_matrix = modelo.mack_covariance_matrix

        # Diagonal principal deve ser igual aos MSEs individuais
        df_mack = modelo.mack_origin_summary
        for ano in self.anos:
            self.assertAlmostEqual(cov_matrix.loc[ano, ano], df_mack.loc[ano, "MSE"], places=4)

        # Covariâncias envolvendo 2022 (totalmente desenvolvido) devem ser zero
        self.assertEqual(cov_matrix.loc[2022, 2023], 0.0)
        self.assertEqual(cov_matrix.loc[2022, 2024], 0.0)

        # Covariância entre 2023 e 2024: 437472 / 121 ~= 3615.47107...
        cov_23_24_esperada = 437472.0 / 121.0
        self.assertAlmostEqual(cov_matrix.loc[2023, 2024], cov_23_24_esperada, places=4)
        self.assertAlmostEqual(cov_matrix.loc[2024, 2023], cov_23_24_esperada, places=4)

        # MSE Total = MSE_2023 + MSE_2024 + 2 * Cov(2023, 2024)
        mse_total_esperado = (
            df_mack.loc[2023, "MSE"]
            + df_mack.loc[2024, "MSE"]
            + 2.0 * cov_23_24_esperada
        )
        self.assertAlmostEqual(modelo.total_mack_mse, mse_total_esperado, places=4)

        # Erro padrão total e CV total
        se_total_esperado = np.sqrt(mse_total_esperado)
        self.assertAlmostEqual(modelo.total_mack_se, se_total_esperado, places=4)
        cv_total_esperado = se_total_esperado / modelo.total_ibnr
        self.assertAlmostEqual(modelo.total_mack_cv, cv_total_esperado, places=4)

        # Decomposição total de risco de processo e risco de parâmetro
        self.assertAlmostEqual(
            modelo.total_mack_mse,
            modelo.total_mack_process_variance + modelo.total_mack_parameter_variance,
            places=4,
        )

    def test_summary_mack_estrutura_e_totais(self):
        modelo = ChainLadder(self.dados, origin_years=self.anos, dev_periods=self.periodos, tail_factor=1.0)
        tab = modelo.summary_mack(include_total=True)

        # Colunas requeridas
        colunas_esperadas = [
            "Safra",
            "Sinistro Acumulado Observado",
            "Fator F_j",
            "Sinistro Final Projetado",
            "Provisão IBNR",
            "Erro Padrão (s.e.)",
            "CV (%)",
        ]
        self.assertListEqual(list(tab.columns), colunas_esperadas)

        # Linha Total presente
        self.assertIn("Total", tab.index)
        self.assertAlmostEqual(tab.loc["Total", "Provisão IBNR"], modelo.total_ibnr, places=4)
        self.assertAlmostEqual(tab.loc["Total", "Erro Padrão (s.e.)"], modelo.total_mack_se, places=4)
        self.assertAlmostEqual(tab.loc["Total", "CV (%)"], modelo.total_mack_cv * 100.0, places=4)


if __name__ == "__main__":
    unittest.main()

