
<p align="center">
  <img src="banner.png" width="800" />
</p>

# Leveraged Pairs Lab — v7 (Trading Room en Vivo Edition)

Aplicación **Streamlit** para análisis cuantitativo de **pares apalancados** (ETF/acciones 2x–3x).  
Compara rendimientos, volatilidades, correlaciones, betas efectivas y simula cobertura simple y avanzada (beta OLS / Theil–Sen / WLS / cointegración).

---

## Instalación y ejecución

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

---

## Arquitectura y flujo general de la app

```mermaid
flowchart LR
  subgraph UI["Streamlit UI"]
    SI["Sidebar: ventana, filtros, tema, botón Actualizar"]
    T1["Resumen (tabla)"]
    T2["Gráficos"]
    T3["Cobertura simple"]
    T4["Cobertura avanzada"]
    T5["Acerca de"]
  end

  subgraph CORE["Core de la App (lógica)"]
    P["pairs.py: listado de pares"]
    M["metrics.py: retornos, vol anualizada, vol 30d, beta OLS, corr, R2"]
    H["hedge.py: calculadora estática"]
    HA["hedge_adv.py: métodos avanzados de cobertura"]
  end

  subgraph DATA["Datos"]
    YF["yfinance: descarga de tickers"]
    C1["Precios cierre"]
    V1["Volumen"]
  end

  SI -->|parametros| YF
  YF --> C1
  YF --> V1
  C1 --> M
  V1 --> M
  P --> M
  M -->|df métricas| T1

  M --> T2
  M --> H
  H --> T3

  C1 --> HA
  HA --> T4

  T5 --> T5

```

---

## Flujo específico: Cobertura avanzada

```mermaid
sequenceDiagram
  participant UI as "Usuario Streamlit"
  participant DL as "Yfinance datos"
  participant HA as "hedge_adv.py"
  participant PL as "Plotly gráficos"

  UI->>DL: Solicitar precios y volumen BASE/ALT en ventana
  DL-->>UI: Series de precios y volumen
  UI->>HA: Calcular retornos BASE y ALT

  alt Metodo beta
    UI->>HA: OLS/Theil-Sen/WLS produce beta constante
  else Cointegracion
    UI->>HA: log(BASE), log(ALT) producen beta y ADF
  end
  HA-->>UI: Beta elegido

  UI->>HA: Simular cobertura (qty_ALT, qty_BASE = -beta*(P_ALT/P_BASE)*qty_ALT)
  HA-->>UI: PnL diario y acumulado

  UI->>HA: Calcular volatilidad anualizada sin/con cobertura
  HA-->>UI: sigma_ALT, sigma_hedged, hedge effectiveness

  UI->>HA: spread = ALT_norm - beta*BASE_norm (bandas 2 sigma)
  HA-->>UI: spread, media, bandas

  UI->>PL: Renderizar PnL, volatilidad, spread y beta rodante
  PL-->>UI: Gráficos interactivos

```

---

## Cálculos clave (resumen)

```mermaid
flowchart TB
  subgraph METRICAS["Métricas"]
    R1["Retornos diarios: r_t = Pt / Pt_1 - 1"]
    V1["Vol anualizada: sigma = sqrt(252) * std(r)"]
    B1["Beta OLS: y = alpha + beta * x + e (x = r_BASE, y = r_ALT)"]
    C1["Correlación: rho = corr(r_BASE, r_ALT)"]
    R2["R2 = 1 - SS_res / SS_tot"]
  end

  subgraph SIMPLE["Cobertura simple spot"]
    H1["shares_BASE = beta*(P_ALT/P_BASE)*qty_ALT"]
    S1["Signo: si ALT largo y beta > 0 entonces BASE corto"]
  end

  subgraph AVZ["Cobertura avanzada histórica"]
    A1["Métodos beta: OLS, Theil-Sen, WLS, Cointegración"]
    A2["Spread = ALT_norm - beta*BASE_norm"]
    A3["PnL_t = qty_ALT*dP_ALT + qty_BASE*dP_BASE"]
    A4["PnL_acum = suma(PnL_t)"]
    A5["Hedge effectiveness = 1 - Var(cubierto)/Var(sin cubrir)"]
  end

  R1 --> V1 --> B1 --> C1 --> R2
  B1 --> H1
  B1 --> A1
  A1 --> A2 --> A3 --> A4 --> A5

```

---

## Autor / Contacto

**Edwin Londoño — Trading Room en Vivo**  
📧 edwin@tradingroomenvivo.com  
📺 [YouTube: Trading Room en Vivo](https://www.youtube.com/@tradingRoomenVivo)  
🌐 [tradingroomenvivo.com](https://www.tradingroomenvivo.com)
