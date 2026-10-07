# Dossiê Técnico & Fundamentação Teórica: Método Chain Ladder e Modelo de Mack (1993)

> **Documento Estruturado para Indexação e Consulta Contínua via Google Drive & NotebookLM**  
> **Área:** Ciências Atuariais (Seguros Não-Vida / Provisões Técnicas & Teoria do Risco)  
> **Autor:** José Eduardo D'Urso — Estudante de Ciências Atuariais da Universidade Federal de Minas Gerais (UFMG)  
> **Projeto:** `analise_sinistros` (Triangulação de Sinistros, IBNR e Incerteza Estocástica)  
> **Implementação em Python:** [`src/chain_ladder.py`](file:///home/jose-eduardo/agente_antigravity/analise_sinistros/src/chain_ladder.py)  
> **Aplicação Web (GitHub Pages):** [`docs/index.html`](file:///home/jose-eduardo/agente_antigravity/analise_sinistros/docs/index.html) | [Live Demo](https://durso16atu.github.io/analise_sinistros/)  
> **Data de Revisão:** Outubro de 2026  

---

## 🧭 Sumário Executivo Conceitual (Pronto para RAG & NotebookLM)

Este sumário sintetiza os conceitos centrais do projeto em tópicos diretos para facilitar respostas assertivas e contextualizadas por agentes inteligentes no NotebookLM:

* **Objeto do Estudo:** Apuração atuarial da provisão de **IBNR** (*Incurred But Not Reported* – Sinistros Ocorridos Mas Não Avisados) e estimativa dos sinistros finais (*Ultimate*) em carteiras de seguros não-vida e resseguros.
* **Ferramenta Fundamental:** Triângulo de Sinistros Acumulados (*Run-Off Triangle*), onde as linhas representam os anos de ocorrência ($i$), as colunas a maturidade de desenvolvimento ($j$) e as diagonais os períodos contábeis ($k = i + j - 1$).
* **Motor Determinístico (Chain Ladder):** Utiliza fatores de desenvolvimento de idade para idade ($f_j$) calculados via média ponderada pelo volume acumulado histórico, projetando o triângulo inferior até a extinção das obrigações com suporte a fator de cauda (*tail factor*).
* **Motor Estocástico (Thomas Mack, 1993):** Modelo não-paramétrico (livre de hipótese distribucional) que deduz analiticamente o erro médio quadrático de predição ($m.s.e.$) e o erro padrão ($s.e.$) da provisão de IBNR, tanto para safras individuais quanto para a carteira total consolidada.
* **Decomposição da Incerteza:** Separa analiticamente a variância em:
  1. *Risco de Processo:* Flutuação aleatória intrínseca da ocorrência futura dos sinistros.
  2. *Risco de Parâmetro:* Incerteza amostral decorrente do número finito de observações históricas usadas para calibrar $f_j$.
* **Correlação entre Safras:** Safras independentes possuem estimativas de IBNR correlacionadas positivamente porque compartilham os mesmos estimadores $\hat{f}_j$. A fórmula de Mack computa a matriz completa de covariância entre anos de ocorrência.
* **Conformidade Regulatória:**
  * **SUSEP (Circular 643/2021 & Resolução CNSP 321/2015):** Exige constituição prudencial de IBNR e testes de consistência da variabilidade das estimativas atuariais.
  * **IFRS 17:** O Chain Ladder fornece o *Best Estimate Liabilities* (BEL) e o erro padrão de Mack subsidia o cálculo do *Risk Adjustment* (RA) via VaR.

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

## 5. Modelagem Estocástica de Thomas Mack (1993)

Embora o método Chain Ladder tradicional produza uma estimativa pontual para a provisão de IBNR, ele não fornece intrinsecamente uma medida de incerteza ou variabilidade estatística associada a essa projeção.

Em seu artigo seminal *"Distribution-free Calculation of the Standard Error of Chain Ladder Reserve Estimates"* (ASTIN Bulletin, 1993), **Thomas Mack** formalizou um modelo probabilístico *livre de hipótese distribucional* (não paramétrico) que preserva os estimadores pontuais clássicos do Chain Ladder e permite deduzir analiticamente:
1. O estimador não tendencioso da **variância residual** de cada período de desenvolvimento ($\hat{\sigma}_j^2$);
2. O **erro médio quadrático de predição** ($m.s.e.$) e o **erro padrão** ($s.e.$) da provisão de cada safra individualmente;
3. A decomposição explícita da incerteza entre **Risco de Processo** e **Risco de Parâmetro**;
4. A **matriz de covariância** entre safras distintas e o **erro padrão consolidado da provisão total agregada** ($s.e.(\hat{R}_{\text{total}})$).

---

### 5.1 Estimação dos Parâmetros de Variância ($\hat{\sigma}_j^2$) e Extrapolação

Para cada transição $j \to j+1$, Mack propôs o estimador não tendencioso da variância residual:

$$\hat{\sigma}_j^2 = \frac{1}{n - j - 1} \sum_{i=1}^{n-j} C_{i, j} \left( \frac{C_{i, j+1}}{C_{i, j}} - \hat{f}_j \right)^2 \quad (1 \le j \le n - 2)$$

* **Graus de Liberdade:** O denominador $n - j - 1$ reflete as $n - j$ observações pareadas disponíveis para a transição $j \to j+1$, subtraído de 1 grau de liberdade consumido pela estimação do parâmetro $\hat{f}_j$.
* **Desvio Padrão Residual:** $\hat{\sigma}_j = \sqrt{\hat{\sigma}_j^2}$.

#### O Problema da Última Transição ($j = n - 1$)
Na última transição observada ($j = n - 1$), há apenas um único par de observações histórico disponível ($i = 1$). Portanto, $n - j = 1$, resultando em denominador $1 - 1 = 0$ (graus de liberdade nulos).

Para contornar essa indeterminação, Mack sugeriu as seguintes técnicas de extrapolação:
1. **Regra de Decaimento Exponencial de Mack (Padrão):**
   Se $\hat{\sigma}_j^2$ for decrescente com o aumento da maturidade $j$, define-se:
   $$\hat{\sigma}_{n-1}^2 = \min\left( \frac{\hat{\sigma}_{n-2}^4}{\hat{\sigma}_{n-3}^2}, \; \min(\hat{\sigma}_{n-3}^2, \hat{\sigma}_{n-2}^2) \right)$$
   *Se $n=3$, onde há apenas um estimador prévio $\hat{\sigma}_1^2$, assume-se $\hat{\sigma}_2^2 = \hat{\sigma}_1^2$. Caso $\hat{f}_{n-1} = 1.0$ (estabilização total sem desenvolvimento), assume-se $\hat{\sigma}_{n-1}^2 = 0$.*
2. **Regra do Mínimo Simples:** $\hat{\sigma}_{n-1}^2 = \min(\hat{\sigma}_{n-2}^2, \hat{\sigma}_{n-3}^2)$.
3. **Regressão Log-Linear:** Ajuste linear de $\ln(\hat{\sigma}_j^2) = \alpha + \beta \cdot j$ sobre os períodos válidos anteriores.

---

### 5.2 Erro Médio Quadrático de Predição ($m.s.e.$) e Erro Padrão ($s.e.$) por Safra

A provisão de IBNR para a safra $i$ é dada por $\hat{R}_i = \hat{C}_{i,n} - C_{i, I_i}$, onde $I_i = n + 1 - i$ é o último período observado de desenvolvimento da safra $i$.

Como o montante observado $C_{i, I_i}$ é constante e conhecido na data base, a incerteza da provisão é idêntica à incerteza do sinistro final projetado $\hat{C}_{i,n}$:
$$m.s.e.(\hat{R}_i) = \mathbb{E}[(R_i - \hat{R}_i)^2 \mid D] = \mathbb{E}[(C_{i,n} - \hat{C}_{i,n})^2 \mid D] = m.s.e.(\hat{C}_{i,n})$$

Thomas Mack deduziu a fórmula analítica recursiva (Mack, 1993, Teorema 1):
$$m.s.e.(\hat{C}_{i,n}) = (\hat{C}_{i,n})^2 \sum_{k=I_i}^{n-1} \frac{\hat{\sigma}_k^2}{\hat{f}_k^2} \left( \frac{1}{\hat{C}_{i,k}} + \frac{1}{S_k} \right)$$
onde:
* $\hat{C}_{i,k}$ é o sinistro acumulado projetado da safra $i$ no estágio de maturação $k$ (para $k = I_i$, coincide com o valor observado $C_{i, I_i}$);
* $S_k = \sum_{m=1}^{n-k} C_{m,k}$ é o volume acumulado histórico observado na coluna $k$ utilizado para estimar $\hat{f}_k$;
* O erro padrão é a raiz quadrada do MSE: $s.e.(\hat{R}_i) = \sqrt{m.s.e.(\hat{R}_i)}$;
* O coeficiente de variação percentual é: $CV_i = \frac{s.e.(\hat{R}_i)}{\hat{R}_i} \times 100\%$.

---

### 5.3 Decomposição Analítica: Risco de Processo vs. Risco de Parâmetro

A fórmula do MSE decompõe-se elegantemente em dois componentes atuariais independentes:

$$m.s.e.(\hat{R}_i) = \underbrace{(\hat{C}_{i,n})^2 \sum_{k=I_i}^{n-1} \frac{\hat{\sigma}_k^2 / \hat{f}_k^2}{\hat{C}_{i,k}}}_{\text{Risco de Processo } (\text{Var}_{\text{proc}})} + \underbrace{(\hat{C}_{i,n})^2 \sum_{k=I_i}^{n-1} \frac{\hat{\sigma}_k^2 / \hat{f}_k^2}{S_k}}_{\text{Risco de Parâmetro } (\text{Var}_{\text{param}})}$$

#### 1. Risco de Processo (*Process Risk*)
* **Conceito:** Variabilidade estocástica intrínseca à realização futura dos sinistros. Mesmo que o atuário soubesse com certeza absoluta os verdadeiros multiplicadores populacionais $f_k$, os pagamentos futuros ainda oscilariam em torno da média esperada.
* **Comportamento:** O termo depende de $\frac{1}{\hat{C}_{i,k}}$. Safras com menor volume individual ou períodos iniciais de maturação apresentam maior risco de processo relativo.

#### 2. Risco de Parâmetro (*Parameter Risk / Estimation Risk*)
* **Conceito:** Incerteza amostral decorrente do fato de que os fatores $\hat{f}_k$ foram calibrados a partir de um conjunto finito de dados históricos limitados ao triângulo de desenvolvimento.
* **Comportamento:** O termo depende de $\frac{1}{S_k} = \frac{1}{\sum_{m=1}^{n-k} C_{m,k}}$. Quanto menor o número de anos históricos que suportam a transição $k \to k+1$, menor é $S_k$ e maior é o risco de parâmetro.

---

### 5.4 Covariância entre Safras e Erro Padrão Total Consolidado

Ao avaliar a solvência de uma seguradora, é imprescindível calcular a volatilidade da **provisão total da carteira**:
$$\hat{R}_{\text{total}} = \sum_{i=2}^n \hat{R}_i$$

O erro médio quadrático agregado é dado por (Mack, 1993, Teorema 2):
$$m.s.e.(\hat{R}_{\text{total}}) = \sum_{i=2}^n m.s.e.(\hat{R}_i) + 2 \sum_{2 \le i < k \le n} \widehat{\text{Cov}}(\hat{C}_{i,n}, \hat{C}_{k,n})$$

#### Por que Safras Independentes têm Provisões Correlacionadas?
Pela Hipótese 2, as safras $i$ e $k$ geram sinistros independentes na realidade física. Entretanto, ao projetarmos seus desenvolvimentos futuros, **ambas utilizam os mesmos fatores estimados $\hat{f}_j$** calculados sobre a base histórica comum.

Se a estimativa $\hat{f}_j$ estiver amostralmente acima do verdadeiro valor médio, ela superestimará simultaneamente a provisão da safra $i$ e a da safra $k$. Essa dependência estocástica compartilhada induz uma **covariância estritamente positiva**.

#### Fórmula da Covariância de Mack
Para duas safras $i < k$ (onde $i$ é mais madura e já alcançou $I_i$, enquanto $k$ é mais recente e alcançou $I_k \le I_i$):
Os períodos futuros comuns a ambas as safras ocorrem a partir de $j = \max(I_i, I_k) = I_i$:

$$\widehat{\text{Cov}}(\hat{C}_{i,n}, \hat{C}_{k,n}) = \hat{C}_{i,n} \cdot \hat{C}_{k,n} \sum_{j = \max(I_i, I_k)}^{n-1} \frac{\hat{\sigma}_j^2}{\hat{f}_j^2 \cdot S_j}$$

> **Propriedade Fundamental:**  
> A fórmula da covariância contém **apenas** o termo de risco de parâmetro $\frac{1}{S_j}$, e **nenhum** termo de risco de processo. Isso ocorre porque os processos geradores de sinistros futuros são independentes entre as safras; toda a correlação entre as provisões decorre exclusivamente do erro de estimação dos parâmetros compartilhados!

---

## 6. Dicionário de Dados Completo

Para referência em modelos de linguagem, relatórios e auditorias atuariais, a tabela abaixo consolida todas as variáveis manipuladas no motor de cálculo:

| Variável / Campo | Tipo de Dado | Notação Matemática | Unidade / Formato | Descrição Técnica & Atuarial |
| :--- | :---: | :---: | :---: | :--- |
| `origin_years` | Lista / Array | $i \in \{1, \dots, n\}$ | Rótulo / Ano | Anos ou períodos de ocorrência dos sinistros (linhas do triângulo). |
| `dev_periods` | Lista / Array | $j \in \{1, \dots, n\}$ | Rótulo / Período | Períodos de desenvolvimento ou maturação (colunas do triângulo). |
| `triangle_original` | Matriz 2D | $C_{i, j}$ | Monetário (R$) | Triângulo de desenvolvimento de sinistros acumulados históricos observados. |
| `tail_factor` | Float | $f_{\text{tail}}$ | Adimensional ($\ge 1.0$) | Fator de cauda para desenvolvimento residual pós-período $n$. |
| `individual_factors` | Vetor | $f_j$ | Razão / Multiplicador | Fatores de transição idade-para-idade entre as maturidades $j$ e $j+1$. |
| `cumulative_factors` | Vetor | $F_j$ (CDF) | Razão / Multiplicador | Fatores acumulados do estágio $j$ até o custo final (*Ultimate*). |
| `projected_triangle` | Matriz 2D | $\hat{C}_{i, j}$ | Monetário (R$) | Triângulo preenchido com as projeções determinísticas de Chain Ladder. |
| `Ultimo_Sinistro_Obs` | Vetor | $C_{i, I_i}$ | Monetário (R$) | Posição financeira observada na data base mais recente da safra $i$. |
| `Sinistro_Final_Ultimate` | Vetor | $\hat{U}_i$ ou $\hat{C}_{i, n}$ | Monetário (R$) | Custo final estimado dos sinistros após desenvolvimento completo. |
| `Provisao_IBNR` | Vetor | $\text{IBNR}_i$ ou $\hat{R}_i$ | Monetário (R$) | Montante de reserva requerido para a safra $i$ ($\hat{U}_i - C_{i, I_i}$). |
| `sigma_squared` | Vetor | $\hat{\sigma}_j^2$ | Variância | Variância residual condicional por coluna de desenvolvimento. |
| `sigma` | Vetor | $\hat{\sigma}_j$ | Desvio Padrão | Desvio padrão residual condicional ($\sqrt{\hat{\sigma}_j^2}$). |
| `Risco_Processo_Var` | Vetor | $\text{Var}_{\text{proc}}(\hat{R}_i)$ | Variância (R$^2$) | Componente de aleatoriedade intrínseca futura do sinistro da safra $i$. |
| `Risco_Parametro_Var` | Vetor | $\text{Var}_{\text{param}}(\hat{R}_i)$ | Variância (R$^2$) | Componente de incerteza amostral dos multiplicadores $f_j$ da safra $i$. |
| `MSE` | Vetor | $m.s.e.(\hat{R}_i)$ | Variância (R$^2$) | Erro médio quadrático de predição total da safra $i$. |
| `Erro_Padrao_se` | Vetor | $s.e.(\hat{R}_i)$ | Monetário (R$) | Erro padrão da estimativa da reserva da safra $i$ ($\sqrt{m.s.e.}$). |
| `CV_pct` | Vetor | $CV_i$ | Percentual (%) | Coeficiente de variação relativo da provisão da safra ($s.e. / \text{IBNR}$). |
| `covariance_matrix` | Matriz $n \times n$ | $\widehat{\text{Cov}}(\hat{R}_i, \hat{R}_k)$ | Variância / Covariância | Matriz com MSEs na diagonal e covariâncias cruzadas fora da diagonal. |
| `total_mack_mse` | Float | $m.s.e.(\hat{R}_{\text{total}})$ | Variância (R$^2$) | MSE agregado da carteira considerando todas as covariâncias entre safras. |
| `total_mack_se` | Float | $s.e.(\hat{R}_{\text{total}})$ | Monetário (R$) | Erro padrão consolidado da provisão agregada de IBNR da entidade. |
| `total_mack_cv` | Float | $CV_{\text{total}}$ | Percentual (%) | Coeficiente de variação consolidado da carteira ($s.e. / \text{IBNR}_{\text{total}}$). |

---

## 7. Interpretação Prática sob a Regulação SUSEP e IFRS 17

### 7.1 Requisitos da SUSEP (Circular nº 643/2021 & Resolução CNSP nº 321/2015)
1. **Obrigatoriedade de Métodos Atuariais Reconhecidos:**  
   O Chain Ladder e o modelo de Mack são metodologias padrão de mercado para apuração do IBNR e validação de suficiência das provisões de sinistros a liquidar.
2. **Monitoramento da Volatilidade e Teste de Consistência (Run-Off Test):**  
   A SUSEP exige que as seguradoras avaliem periodicamente se suas reservas históricas foram suficientes para cobrir as liquidações reais subsequentes. O erro padrão de Mack ($s.e.$) serve como balizador objetivo: se a diferença entre a reserva constituída e a realidade for recorrentemente superior a $2 \cdot s.e.$, há indício de deficiência estrutural de parametrização.

### 7.2 Norma Internacional IFRS 17 (*Insurance Contracts*)
Sob o IFRS 17, a mensuração do passivo de sinistros incorridos (*Liability for Incurred Claims - LIC*) é estruturada em blocos:

$$\text{LIC} = \text{Best Estimate Liabilities (BEL)} + \text{Risk Adjustment (RA)} + \text{Efeito do Desconto Financeiro (se relevante)}$$

* **Best Estimate Liabilities (BEL):** O valor pontual da provisão de IBNR apurado pelo Chain Ladder ponderado por volume representa o valor esperado neutro ao risco dos fluxos de caixa futuros.
* **Risk Adjustment for Non-Financial Risk (RA):** O modelo estocástico de Mack fornece a medida analítica exata da incerteza não-financeira ($s.e.(\hat{R}_{\text{total}})$). O RA pode ser calculado diretamente pelo método de *Cost of Capital* ou pela técnica de *Value at Risk (VaR)*:
  $$\text{RA}_{\alpha} = z_{\alpha} \cdot s.e.(\hat{R}_{\text{total}})$$
  onde $z_{\alpha}$ é o quantil da distribuição normal ou log-normal correspondente ao nível de confiança pretendido pela governança da seguradora (por exemplo, 75% ou 90%).

---

## 8. Fluxo Operacional: Sincronização Google Drive & NotebookLM

Para manter este repositório perfeitamente sincronizado com bases de conhecimento no **Google Drive** e no **Google NotebookLM**, siga o fluxo operacional abaixo:

### Passo 1: Localização e Estrutura de Arquivos
* O arquivo mestre de conhecimento é o [`docs/notebooklm_contexto.md`](file:///home/jose-eduardo/agente_antigravity/analise_sinistros/docs/notebooklm_contexto.md).
* Ele foi redigido com formatação GFM (*GitHub Flavored Markdown*) e equações LaTeX, o que garante renderização nativa de alta fidelidade no NotebookLM.

### Passo 2: Sincronização com o Google Drive
* **Opção 1 (Google Drive para Desktop):** Se você utiliza o cliente oficial do Google Drive montado em sua máquina, crie um link simbólico ou copie os arquivos da pasta `docs/` para a pasta do Drive:
  ```bash
  # Exemplo de cópia para pasta do Drive montada
  cp docs/notebooklm_contexto.md ~/GoogleDrive/Atuaria_UFMG/analise_sinistros/
  ```
* **Opção 2 (Upload Manual ou via Web):** Faça o upload de `docs/notebooklm_contexto.md` diretamente para a pasta do seu projeto no Google Drive.

### Passo 3: Criação da Fonte de Conhecimento no NotebookLM
1. Acesse o **Google NotebookLM** ([notebooklm.google.com](https://notebooklm.google.com/)).
2. Crie um novo caderno de estudos: *"Atuária Quant - Provisões Técnicas & Mack (1993)"*.
3. Clique em **"Adicionar Fonte"** e selecione **Google Drive** (ou faça upload do arquivo `.md`).
4. Selecione o arquivo `notebooklm_contexto.md`.
5. O NotebookLM indexará instantaneamente todo o sumário conceitual, fórmulas, premissas de independência e tabelas explicativas, permitindo geração de resumos executivos, guias de estudo, áudios explicativos (*Audio Overviews*) e respostas técnicas fundamentadas.

---

## 9. Perguntas Frequentes (FAQ Expandido para o NotebookLM)

### P1: O que diferencia o IBNR calculado sobre sinistros pagos do IBNR sobre sinistros avisados?
**R:** Quando o Chain Ladder é aplicado ao triângulo de **sinistros pagos**, a projeção indica o montante total a pagar até o encerramento da carteira (o que inclui tanto a PSL quanto o IBNR estrito). Quando aplicado ao triângulo de **sinistros avisados/incorridos** (pagos + PSL caso a caso), o resultado projeta o custo final corrigindo tanto os não avisados (*Pure IBNR*) quanto a insuficiência das reservas individuais (*IBNER*).

### P2: Por que a média ponderada pelo volume é a preferida na prática atuarial em relação à média simples?
**R:** Sob as hipóteses do modelo estocástico de Mack (1993), a variância dos sinistros é proporcional ao volume acumulado. A média ponderada dá peso proporcional aos anos de ocorrência com maior volume financeiro, conferindo robustez contra distorções causadas por anos com volume reduzido, além de ser o estimador linear de variância mínima (*BLUE*).

### P3: Qual é a diferença prática entre Risco de Processo e Risco de Parâmetro?
**R:** O **Risco de Processo** reflete a pura aleatoriedade futura dos sinistros que irão ocorrer ou ser avisados (volatilidade natural do negócio segurador). O **Risco de Parâmetro** reflete a nossa ignorância amostral sobre a verdadeira média histórica de desenvolvimento ($f_k$), devido à limitação de anos observados no triângulo. Quanto maior a base de dados histórica da seguradora, menor é o Risco de Parâmetro, mas o Risco de Processo permanece existente.

### P4: Por que a covariância entre safras nunca é negativa no modelo de Mack?
**R:** Porque a covariância é gerada exclusivamente pelo uso dos mesmos multiplicadores $\hat{f}_j$. Como todos os volumes de sinistros observados $S_j$ e variâncias $\hat{\sigma}_j^2$ são não negativos, o termo $\frac{\hat{\sigma}_j^2}{\hat{f}_j^2 \cdot S_j}$ é estritamente $\ge 0$. Logo, qualquer perturbação positiva em $\hat{f}_j$ aumenta as projeções de todas as safras que necessitam passar por esse período de desenvolvimento.

### P5: Por que o Coeficiente de Variação da carteira total ($CV_{\text{total}}$) é menor que o das safras recentes?
**R:** Esse é o efeito clássico de **diversificação atuarial**. Como os riscos de processo entre anos de ocorrência distintos são descorrelacionados, as flutuações aleatórias individuais tendem a se compensar parcialmente na agregação, reduzindo a variabilidade percentual da carteira em relação à provisão total.

### P6: Como o atuário utiliza o erro padrão de Mack sob as normas da SUSEP e do IFRS 17?
**R:** No **IFRS 17**, a provisão para sinistros incorridos (*Liability for Incurred Claims - LIC*) é dividida entre o Fluxo de Caixa Estimado (*Best Estimate Liabilities - BEL*) e o Ajuste de Risco Não Financeiro (*Risk Adjustment - RA*). O método de Mack fornece a estimativa do BEL (a provisão clássica de IBNR) e a base estocástica exata ($s.e.$) para calcular o *Risk Adjustment* em níveis de confiança prudenciais (por exemplo, percentil 75% ou 90% via Value at Risk / VaR).

---

<p align="center">
  <em>Dossiê preparado para Ciências Atuariais - UFMG | Referência para NotebookLM e Gestão Documental via Google Drive.</em>
</p>
