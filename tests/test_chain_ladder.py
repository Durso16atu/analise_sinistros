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


if __name__ == "__main__":
    unittest.main()
