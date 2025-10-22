

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
  subgraph UI[Streamlit UI]
    SI[Sidebar: Ventana, Filtros, Tema, Boton Actualizar]
    T1[Resumen (tabla)]
    T2[Graficos]
    T3[Cobertura simple]
    T4[Cobertura avanzada]
    T5[Acerca de]
  end

  subgraph Core[Core de la App (logica)]
    P[pairs.py: listado de pares (BASE->ALT, target_ratio, emisor, nota)]
    M[metrics.py: retornos, vol anualizada, volumen 30d, beta OLS, corr, R2]
    H[hedge.py: calculadora estatica -> shares_BASE = beta*(P_ALT/P_BASE)*qty_ALT]
    HA[hedge_adv.py: beta OLS/Theil-Sen/WLS/cointegracion, beta rodante, simulador PnL, hedge effectiveness]
  end

  subgraph Data[Datos]
    YF[yfinance: download(tickers, start, end)]
    C1[Close (series por ticker)]
    V1[Volume (series por ticker)]
  end

  SI -->|Parametros| YF
  YF --> C1
  YF --> V1
  C1 --> M
  V1 --> M
  P --> M
  M -->|DataFrame de metricas| T1

  M -->|Metricas| T2
  T2 -->|Lollipop beta vs target| T2
  T2 -->|Desviacion beta| T2
  T2 -->|Riesgo-Retorno (burbujas)| T2
  T2 -->|Retornos acumulados ALT| T2
  T2 -->|Retornos acumulados BASE vs ALT| T2
  T2 -->|Beta rodante| T2

  M --> H
  H -->|resultado spot| T3

  C1 --> HA
  HA -->|beta metodo elegido| T4
  HA -->|Spread ALT - beta*BASE| T4
  HA -->|PnL acumulado y Vol cubierta| T4
  HA -->|Hedge Effectiveness| T4

  T5 -->|Autor y Contacto| T5
```
  
---

## Flujo especifico: Cobertura avanzada

```mermaid
sequenceDiagram
  participant UI as Usuario (Streamlit)
  participant DL as yfinance (datos)
  participant HA as hedge_adv.py
  participant PL as Plotly (graficos)

  UI->>DL: Solicita Close/Volume (BASE, ALT) en ventana
  DL-->>UI: Series de precios/volumen
  UI->>HA: returns(BASE), returns(ALT)

  alt Metodo beta
    UI->>HA: OLS / Theil-Sen / WLS -> beta (constante)
  else Cointegracion
    UI->>HA: log(BASE), log(ALT) -> beta + ADF(p)
  end
  HA-->>UI: beta elegido

  UI->>HA: Simular cobertura con qty_ALT y qty_BASE = - beta * (P_ALT/P_BASE) * qty_ALT (spot)
  HA-->>UI: Serie PnL diaria y PnL acumulado

  UI->>HA: Calcular vol anualizada (sin cobertura vs cubierta)
  HA-->>UI: sigma_ALT, sigma_hedged, HedgeEffectiveness = 1 - Var(covered)/Var(unhedged)

  UI->>HA: Spread = ALT_norm - beta*BASE_norm (bandas +-2*sigma)
  HA-->>UI: Spread, media y bandas

  UI->>PL: Render PnL, Vol, Spread, beta rodante
  PL-->>UI: Graficos interactivos (tema oscuro)
```

---

## Calculos clave (resumen)

```mermaid
flowchart TB
  subgraph Metricas
    R1[Retornos diarios: r_t = P_t / P_{t-1} - 1]
    V1[Vol anualizada: sigma = sqrt(252) * std(r)]
    B1[Beta (OLS): y = alpha + beta*x + e, con x=r_BASE, y=r_ALT]
    C1[Correlacion: rho = corr(r_BASE, r_ALT)]
    R2[R2 = 1 - SS_res/SS_tot]
  end

  subgraph SimpleHedge[ Cobertura simple (spot) ]
    H1[shares_BASE = beta * (P_ALT / P_BASE) * qty_ALT]
    S1[Signo: si ALT largo y beta>0 => BASE corto]
  end

  subgraph Avanzado[ Cobertura avanzada (historica) ]
    A1[Metodos de beta: OLS / Theil-Sen / WLS / Cointegracion]
    A2[Spread = ALT_norm - beta*BASE_norm]
    A3[PnL_t = qty_ALT * dP_ALT + qty_BASE * dP_BASE]
    A4[PnL_acum = suma(PnL_t)]
    A5[Hedge Effectiveness = 1 - Var(covered)/Var(unhedged)]
  end

  R1 --> V1 --> B1 --> C1 --> R2
  B1 --> H1
  B1 --> A1
  A1 --> A2 --> A3 --> A4 --> A5
```

---

## Autor / Contacto
Edwin Londono — Trading Room en Vivo  
Email: edwin@tradingroomenvivo.com   
YouTube: https://www.youtube.com/@tradingRoomenVivo  
Sitio: https://www.tradingroomenvivo.com