# FT Visual Vocabulary & Visual Sandbox — Helse og Mestring

## De 9 Kognitive Kategoriene (Alan Smith / Financial Times) & 36 Visuals Suite

1. **Deviation**: RAG-Trafikklys & Netto avvik i prosent (§ 14-5)
2. **Correlation**: Scatterplot over Sykefravær (%) vs. Vikar-/Overtidsutgifter (art 109000/110000) per enhet
3. **Ranking**: Minimal Ink Lollipop Charts for Cost Performance Index (CPI)
4. **Distribution**: Box Plot & Whiskers for sykefravær per døgnomsorgsavdeling
5. **Change over Time**: Monte Carlo Fan Charts (Usikkerhetsvifter P10/P50/P90)
6. **Magnitude**: Treemaps over Helse og Mestrings totalramme (1,85 mrd)
7. **Part-to-Whole**: Waterfall (Budsjettbro) fra vedtatt ramme (BAC) til justert årsprognose (EAC)
8. **Spatial**: Bydelskart over Kristiansand med belastningsgrad
9. **Flow**: Sankey-diagrammer over pengestrøm fra statstilskudd til sykehjem

## Edward Tufte Principles
- **Maximize Data-Ink Ratio**: Fjern tunge bakgrunner, vertikale rutenett og dekorasjon.
- **Direct Labeling**: Bruk direkte etikettering på tidsserier og S-kurver fremfor separate fargelegender.
- **Micro/Macro Design**: Tillat direkte drill-down fra sektornivå ned til enkeltbilag.

---

## 🕒 Time-Visuals Suite (Time-Visuals.pdf - 60 Ways to Visualize Time)

For å støtte kommunale ledere i å forstå tidsutvikling, månedlige avvik og usikkerhet i helårsprognoser, inneholder Visual Sandboxen komplette maler fra **Time-Visuals.pdf**:

1. **01-03 Discrete & Continuous Line Charts**: Grunnleggende tidsserier med Tufte-merking.
2. **11 Moving Average (3M Glidende Snitt)**: Glatting av sesongsvingninger på vikarbyrå og overtid.
3. **16-17 Stacked Area & % of Total**: Komponentutvikling i fastlønn, overtid, vikar og refusjoner over 12 måneder.
4. **23-25 Running Total Area Charts**: Akkumulerte utgifter og avvik YTD mot periodisert budsjett (BAC).
5. **38 Cycle Plot**: Analyser av månedlige fraværs- og vikarutgiftstopper over flere år.
6. **40-41 Slope Graphs**: Sammenligning av 1. tertial (T1) vs. 2. tertial (T2) per omsorgsenhet.
7. **46 Sparklines**: Edward Tufte mikrografer for rask konsernskanning på 2 sekunder.
8. **56-58 Connected Scatterplot**: Viser dynamisk faseforskyvning mellom sykefravær (%) og EAC helårsprognose (MNOK).
9. **59 Waterfall Chart**: Budsjettbro fra vedtatt BAC til regulert EAC.

### 🤖 AI Chat Integration
Når en leder stiller spørsmål til AI Controller Chatbot om utvikling eller avvik over tid, kjører agenten `recommend_visual_for_chat_response()` og foreslår den mest relevante diagramtypen direkte i chat-responsen!
