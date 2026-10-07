# Fundamentação Teórica: Método Chain Ladder e Provisão de IBNR

> **Guia Conceitual e Atuarial para NotebookLM**  
> **Tema:** Triangulação de Sinistros, Modelo de Mack, Estimativa de Sinistros Finais (*Ultimate*) e Cálculo de IBNR (*Incurred But Not Reported*).  
> **Referência de Implementação:** [`src/chain_ladder.py`](file:///home/jose-eduardo/agente_antigravity/analise_sinistros/src/chain_ladder.py)

---

## 1. Visão Geral e Contexto de Negócio

No setor de seguros e resseguros, existe uma defasagem temporal inevitável entre três marcos fundamentais:
1. **A ocorrência do evento gerador** (*Accident Date* ou Data do Sinistro);
2. **A notificação formal à seguradora** (*Reporting Date* ou Data do Aviso);
3. **A liquidação financeira final do sinistro** (*Settlement Date* ou Data do Pagamento).

Em virtude desse atraso operacional e jurídico (*claims lag*), na data de fechamento contábil e atuarial, a seguradora possui compromissos financeiros já gerados sobre os quais ainda não foi avisada, ou sobre os quais o valor inicial avisado ainda passará por revisões de valor.

Para manter sua solvência e cumprir os requisitos prudenciais (como os da **SUSEP** no Brasil e as normas internacionais do **IFRS 17**), a entidade deve constituir reservas técnicas de sinistros a liquidar.

### 1.1 Classificação das Provisões de Sinistros
* **PSL (Provisão de Sinistros a Liquidar):** Estimativa dos sinistros já avisados à seguradora, mas ainda não totalmente pagos até a data base. Baseia-se no valor estimado caso a caso pelos reguladores de sinistros (*case reserves*).
* **IBNR (*Incurred But Not Reported* - Sinistros Ocorridos Mas Não Avisados):** Sinistros cujos eventos geradores ocorreram dentro do período de vigência das apólices até a data de avaliação, porém ainda não foram comunicados à seguradora.
* **IBNER (*Incurred But Not Enough Reported*):** Desenvolvimento futuro e insuficiência dos valores provisionados nos sinistros já avisados (revisões de laudos periciais, decisões judiciais, inflação médica, etc.).
* **IBNR Amplo (Pure IBNR + IBNER):** Quando o triângulo de desenvolvimento é construído sobre dados de sinistros avisados/incorridos acumulados (*Incurred Claims*), o Chain Ladder projeta o desenvolvimento total futuro, capturando tanto o IBNR estrito quanto o IBNER. Se construído sobre sinistros pagos (*Paid Claims*), projeta o montante total pendente de pagamento até a extinção das obrigações.

---

## 2. Estrutura do Triângulo de Desenvolvimento (*Run-Off Triangle*)

A ferramenta fundamental para estimação de IBNR é o **Triângulo de Sinistros** (também chamado de Triângulo de *Run-off* ou Matriz de Desenvolvimento).

### 2.1 Dimensões do Triângulo
* **Linhas ($i = 1, 2, \dots, n$):** Períodos de Ocorrência (*Accident Periods* / Anos ou Trimestres de Origem).
* **Colunas ($j = 1, 2, \dots, n$):** Períodos de Desenvolvimento (*Development Periods* / Maturidade temporal desde a ocorrência: 1º ano, 2º ano, etc.).
* **Diagonais ($k = i + j - 1$):** Períodos de Calendário Contábil (*Calendar/Accounting Periods*).
  * A diagonal principal ($i + j - 1 = n$) representa a data de avaliação mais recente (posição atual do balanço).
  * O triângulo superior ($i + j - 1 \le n$) contém os sinistros históricos observados.
  * O triângulo inferior ($i + j - 1 > n$) contém os períodos futuros ainda não observados, que precisam ser estimados pelo atuário.

### 2.2 Sinistros Incrementais vs. Acumulados
Sejam:
* $X_{i,j}$: Sinistros incrementais do ano de ocorrência $i$ pagos/avisados no período de desenvolvimento $j$.
* $C_{i,j}$: Sinistros acumulados do ano de ocorrência $i$ até o período de desenvolvimento $j$:
$$C_{i,j} = \sum_{k=1}^{j} X_{i,k}$$

O método Chain Ladder opera primariamente sobre o triângulo **acumulado** $C_{i,j}$, pois assume que o valor acumulado em um estágio $j$ guarda uma proporção estável com o valor acumulado no estágio imediatamente posterior $j+1$.

---

## 3. Hipóteses Atuariais do Método Chain Ladder (Modelo de Mack, 1993)

Thomas Mack formalizou o arcabouço probabilístico e as premissas estocásticas que justificam a validade estatística do método Chain Ladder clássico através de três hipóteses centrais:

### Hipótese 1: Independência entre Anos de Ocorrência
> **Formalização:** As variáveis $\{C_{i, 1}, C_{i, 2}, \dots, C_{i, n}\}$ e $\{C_{k, 1}, C_{k, 2}, \dots, C_{k, n}\}$ são mutuamente independentes para quaisquer anos de ocorrência distintos $i \neq k$.

* **Significado Atuarial:** O comportamento de avisos e liquidações de uma safra anterior (ex: sinistros de 2021) não exerce influência estatística direta sobre o processo gerador de sinistros de uma safra subsequente (ex: sinistros de 2023). Cada ano de ocorrência se desenvolve como um processo estocástico autônomo.

### Hipótese 2: Estabilidade e Proporcionalidade do Padrão de Desenvolvimento
> **Formalização:** Existem fatores positivos $f_1, f_2, \dots, f_{n-1} > 0$ tais que:
> $$\mathbb{E}\left[C_{i, j+1} \mid C_{i, 1}, C_{i, 2}, \dots, C_{i, j}\right] = \mathbb{E}\left[C_{i, j+1} \mid C_{i, j}\right] = f_j \cdot C_{i, j}$$
> para todo ano de ocorrência $i \in \{1, \dots, n\}$ e estágio $j \in \{1, \dots, n-1\}$.

* **Significado Atuarial:** 
  1. **Propriedade Markoviana:** Dado o conhecimento da posição acumulada no estágio $j$ ($C_{i, j}$), a trajetória anterior ($C_{i, 1}, \dots, C_{i, j-1}$) não agrega informação preditiva adicional para o valor esperado de $C_{i, j+1}$.
  2. **Homogeneidade Temporal:** O fator de desenvolvimento $f_j$ depende unicamente do estágio de desenvolvimento $j$, sendo constante e idêntico para todos os anos de ocorrência $i$.

### Hipótese 3: Estrutura de Variância (Dispersão Proporcional)
> **Formalização:** Existem parâmetros de variância $\sigma_1^2, \sigma_2^2, \dots, \sigma_{n-1}^2 > 0$ tais que:
> $$\mathrm{Var}\left(C_{i, j+1} \mid C_{i, 1}, C_{i, 2}, \dots, C_{i, j}\right) = \mathrm{Var}\left(C_{i, j+1} \mid C_{i, j}\right) = \sigma_j^2 \cdot C_{i, j}$$

* **Significado Atuarial:** A variância condicional do sinistro acumulado no estágio seguinte é proporcional ao volume acumulado no estágio atual. Sob essa condição de heterocedasticidade, pelo Teorema de Gauss-Markov, o estimador de **média ponderada pelo volume** é o estimador linear não enviesado de variância mínima (*BLUE - Best Linear Unbiased Estimator*) para os fatores de desenvolvimento $f_j$.

### Hipótese Implícita: Ausência de Distorções Graves do Ano Calendário
O Chain Ladder clássico pressupõe que não há efeitos diagonais abruptos (como hiperinflação imprevista, mudanças drásticas na legislação de trânsito, reformas judiciais ou pandemias) que afetem simultaneamente todos os anos de ocorrência em um mesmo ano calendário sem que o atuário realize ajustes prévios ou expurgos.

---

## 4. Passo a Passo Matemático dos Cálculos

### 4.1 Fatores de Desenvolvimento Individuais ($f_j$)
Os fatores individuais (também chamados de *link ratios*, fatores de idade-para-idade ou *age-to-age factors*) quantificam o crescimento percentual esperado do montante de sinistros acumulados da maturidade $j$ para a maturidade $j+1$.

O estimador atuarial padrão (média ponderada pelo volume histórico disponível) é dado por:
$$f_j = \frac{\sum_{i=1}^{n-j} C_{i, j+1}}{\sum_{i=1}^{n-j} C_{i, j}}$$

*Alternativas metodológicas:*
* **Média Aritmética Simples:** $\bar{f}_j = \frac{1}{n-j} \sum_{i=1}^{n-j} \frac{C_{i, j+1}}{C_{i, j}}$
* **Média Móvel dos Últimos $m$ Anos:** Utilizada quando há tendência recente de aceleração ou desaceleração operacional na regulação de sinistros.

### 4.2 Fator de Cauda (*Tail Factor*)
Em carteiras de cauda longa (*long-tail liabilities*), como Responsabilidade Civil Geral, D&O ou Riscos de Engenharia, os sinistros continuam a se desenvolver mesmo após o último período registrado no triângulo ($j = n$).

O fator de cauda ($\text{tail\_factor} \ge 1.0$) projeta o desenvolvimento residual do estágio $n$ até a extinção definitiva dos sinistros (*Ultimate*):
$$f_{\text{tail}} = \frac{C_{i, \infty}}{C_{i, n}}$$
Se não houver desenvolvimento esperado após o período $n$, adota-se $\text{tail\_factor} = 1.0$.

### 4.3 Fatores Acumulados de Desenvolvimento ($F_j$ ou CDF)
O Fator Acumulado de Desenvolvimento (*Cumulative Development Factor* - CDF), denotado por $F_j$, é o multiplicador que projeta o sinistro acumulado do estágio $j$ diretamente para o custo final estimado (*Ultimate*):

$$F_j = \left( \prod_{k=j}^{n-1} f_k \right) \times \text{tail\_factor}$$

Para o período final $n$:
$$F_n = \text{tail\_factor}$$

Propriedade ordinal obrigatória:
$$F_1 > F_2 > \dots > F_{n-1} \ge F_n \ge 1.0$$

### 4.4 Projeção do Triângulo Inferior
Para cada célula não observada do triângulo inferior ($i + j - 1 > n$), a projeção sequencial é obtida recursivamente a partir do valor imediatamente anterior:
$$\hat{C}_{i, j} = \hat{C}_{i, j-1} \times f_{j-1}$$

### 4.5 Estimativa dos Sinistros Finais (*Ultimate Losses*)
Para cada ano de ocorrência $i$, seja $C_{i, j_{\text{obs}}}$ o sinistro acumulado mais recente disponível (situado na diagonal observada do triângulo, onde $j_{\text{obs}} = n - i + 1$).

O sinistro final esperado ($\hat{U}_i$ ou $\hat{C}_{i, \infty}$) é calculado diretamente pelo produto do valor atual pelo seu respectivo fator acumulado:
$$\hat{U}_i = C_{i, j_{\text{obs}}} \times F_{j_{\text{obs}}}$$

### 4.6 Provisão de IBNR por Ano de Ocorrência e Total
A provisão de IBNR para o ano de ocorrência $i$ é a diferença entre o sinistro final esperado e o total de sinistros acumulados já conhecidos na data base:
$$\text{IBNR}_i = \hat{U}_i - C_{i, j_{\text{obs}}} = C_{i, j_{\text{obs}}} \times (F_{j_{\text{obs}}} - 1)$$

A **Provisão Total de IBNR** da carteira é o somatório de todos os anos de ocorrência:
$$\text{IBNR}_{\text{total}} = \sum_{i=1}^{n} \text{IBNR}_i$$

---

## 5. Exemplo Numérico Passo a Passo

Considere o triângulo acumulado de 3 anos de ocorrência e 3 estágios de desenvolvimento (valores em milhares de reais):

| Ano Ocorrência | Dev 1 | Dev 2 | Dev 3 |
| :--- | :---: | :---: | :---: |
| **2022** | 1.000 | 1.500 | 1.800 |
| **2023** | 1.200 | 1.860 | — |
| **2024** | 1.400 | — | — |

Assumindo `tail_factor = 1.0`:

### Passo 1: Fatores Individuais ($f_j$)
* $f_1$ (Dev 1 $\to$ Dev 2):
  $$f_1 = \frac{C_{2022, 2} + C_{2023, 2}}{C_{2022, 1} + C_{2023, 1}} = \frac{1.500 + 1.860}{1.000 + 1.200} = \frac{3.360}{2.200} = 1{,}5273$$
* $f_2$ (Dev 2 $\to$ Dev 3):
  $$f_2 = \frac{C_{2022, 3}}{C_{2022, 2}} = \frac{1.800}{1.500} = 1{,}2000$$

### Passo 2: Fatores Acumulados ($F_j$)
* $F_3 = \text{tail\_factor} = 1{,}0000$
* $F_2 = f_2 \times F_3 = 1{,}2000 \times 1{,}0000 = 1{,}2000$
* $F_1 = f_1 \times F_2 = 1{,}5273 \times 1{,}2000 = 1{,}8328$

### Passo 3: Projeção de Ultimate e IBNR
* **Ano 2022 (Dev 3):**
  * Último observado: $1.800$
  * Fator $F_3 = 1{,}0000$
  * $\text{Ultimate}_{2022} = 1.800 \times 1{,}0000 = 1.800{,}00$
  * $\text{IBNR}_{2022} = 1.800 - 1.800 = 0{,}00$
* **Ano 2023 (Dev 2):**
  * Último observado: $1.860$
  * Fator $F_2 = 1{,}2000$
  * $\text{Ultimate}_{2023} = 1.860 \times 1{,}2000 = 2.232{,}00$
  * $\text{IBNR}_{2023} = 2.232{,}00 - 1.860 = 372{,}00$
* **Ano 2024 (Dev 1):**
  * Último observado: $1.400$
  * Fator $F_1 = 1{,}8328$
  * $\text{Ultimate}_{2024} = 1.400 \times 1{,}8328 = 2.565{,}92$
  * $\text{IBNR}_{2024} = 2.565{,}92 - 1.400 = 1.165{,}92$

**Provisão Total de IBNR:** $0{,}00 + 372{,}00 + 1.165{,}92 = \mathbf{1.537{,}92}$

---

## 6. Limitações Críticas e Boas Práticas Atuariais

Embora seja o método mais difundido mundialmente, o Chain Ladder possui vulnerabilidades operacionais que exigem julgamento atuarial crítico:

1. **Sensibilidade em Anos Muito Recentes (*Leveraging Effect*):**
   * No ano mais recente ($i = n$), o estágio de maturidade é 1. Como $F_1$ costuma ser expressivo, qualquer oscilação pontual aleatória em $C_{n, 1}$ é multiplicada e amplificada na estimativa do *Ultimate*. Em anos imaturos, métodos como **Bornhuetter-Ferguson (BF)** ou **Cape Cod**, que incorporam o prêmio ganho e uma sinistralidade a priori, tendem a ser mais estáveis.
2. **Alterações nos Procedimentos de Regulação de Sinistros:**
   * Se a equipe de sinistros acelerar os avisos ou pagamentos (ou, ao contrário, houver represamento), a velocidade histórica de desenvolvimento é distorcida, fazendo com que o Chain Ladder superestime ou subestime severamente as provisões.
3. **Presença de Sinistros Atípicos (*Outliers* ou Grandes Sinistros):**
   * Sinistros de severidade extraordinária distorcem a razão entre colunas. A prática atuarial recomenda expurgar os sinistros atípicos, calcular o Chain Ladder sobre a massa homogênea (sinistros de atrito) e adicionar a reserva de grandes sinistros individualmente.
4. **Valores Negativos:**
   * Recuperações judiciais, ressarcimentos ou salvados que superem os sinistros de um período podem gerar incrementos negativos, exigindo tratamento específico para evitar inconsistências nas divisões.

---

## 7. Mapeamento dos Componentes do Código Python

A implementação contida no arquivo [`src/chain_ladder.py`](file:///home/jose-eduardo/agente_antigravity/analise_sinistros/src/chain_ladder.py) traduz rigorosamente os conceitos matemáticos acima:

| Conceito Atuarial | Símbolo Matemático | Método / Propriedade no Código | Descrição Operacional |
| :--- | :---: | :--- | :--- |
| Triângulo Acumulado | $C_{i,j}$ | `triangle_original` | DataFrame padronizado com linhas=ocorrência e colunas=desenvolvimento. |
| Fator de Desenvolvimento | $f_j$ | `calculate_development_factors()` / `individual_factors` | Média ponderada por volume entre pares válidos consecutivos de colunas. |
| Fator Acumulado / CDF | $F_j$ | `calculate_cumulative_factors()` / `cumulative_factors` | Produtório reverso de $f_j$ até a maturidade, multiplicado por `tail_factor`. |
| Fator de Cauda | $f_{\text{tail}}$ | `tail_factor` | Parâmetro do construtor (default=1.0) para expansão além do período $n$. |
| Triângulo Projetado | $\hat{C}_{i,j}$ | `project_triangle()` / `projected_triangle` | Preenche células inferiores ($i+j-1 > n$) com a recursão $\hat{C}_{prev} \times f$. |
| Sinistro Final | $\hat{U}_i$ | `calculate_ibnr()['Sinistro_Final_Ultimate']` | Produto do último valor observado na linha pelo respectivo $F_j$. |
| Provisão de IBNR | $\text{IBNR}_i$ | `calculate_ibnr()['Provisao_IBNR']` | Diferença entre o Sinistro Final Estimado e o último valor observado. |
| IBNR Total Consolidado | $\sum \text{IBNR}_i$ | `total_ibnr` | Soma escalar de todos os IBNRs calculados na carteira. |
| Relatório Formatado | — | `format_results()` | String estruturada e amigável contendo todas as tabelas e totais em R$. |

---

## 8. Perguntas Frequentes (FAQ para o NotebookLM)

### P1: O que diferencia o IBNR calculado sobre sinistros pagos do IBNR sobre sinistros avisados?
**R:** Quando o Chain Ladder é aplicado ao triângulo de **sinistros pagos**, a projeção indica o montante total a pagar até o encerramento da carteira (o que inclui tanto a PSL quanto o IBNR estrito). Quando aplicado ao triângulo de **sinistros avisados/incorridos** (pagos + PSL caso a caso), o resultado projeta o custo final corrigindo tanto os não avisados (*Pure IBNR*) quanto a insuficiência das reservas individuais (*IBNER*).

### P2: Por que a média ponderada pelo volume é a preferida na prática atuarial em relação à média simples?
**R:** Sob as hipóteses do modelo estocástico de Mack (1993), a variância dos sinistros é proporcional ao volume acumulado. A média ponderada dá peso proporcional aos anos de ocorrência com maior volume financeiro, conferindo robustez contra distorções causadas por anos com volume reduzido, além de ser o estimador linear de variância mínima (*BLUE*).

### P3: Quando um atuário deve utilizar um fator de cauda (*tail factor*) maior que 1.0?
**R:** Sempre que na última coluna do triângulo ($j = n$) ainda for constatado desenvolvimento residual de sinistros (pagamentos ou avisos tardios), comum em ramos de cauda longa (*long tail*), como Responsabilidade Civil, Riscos Ambientais e Garantia.

### P4: O que acontece se o triângulo possuir células vazias no meio dos dados históricos?
**R:** O cálculo de $f_j$ filtra rigorosamente apenas os pares de anos em que ambos os estágios $j$ e $j+1$ foram observados e são estritamente positivos. Caso um triângulo contenha lacunas no meio (*holes*), o atuário deve investigar a integridade da base contábil antes de projetar.

---
*Documento preparado como fonte de conhecimento técnico para agentes atuariais e modelos de linguagem no NotebookLM.*
