# Memory market trends since July 2026: research for the November model update

Compiled 2026-11-07. Scope: what was published or announced from about July 2026 onward that bears on
`memoryProjection/assumptions/*.yaml`. Micron and SK hynix earnings are covered by another session and
appear here only as context.

**How to read each entry.** Each finding gives the claim, the source and its publication date, a
confidence tag, and the YAML key(s) it bears on with their current values. The verdict uses three labels:
**SUPPORTS** (consistent with the current value), **CONTRADICTS** (the value should move), or **MIXED**.

**Caveat on sources.** Many results came through secondary aggregators. Where I opened a primary page
(TrendForce press center, company transcripts), I say so. Where sources disagree, I give the range.
TrendForce's own 3Q26 DRAM and NAND revenue rankings have not been published yet; they usually appear in
early December. Treat every 3Q26 industry-total figure below as derived.

**Cross-cutting point that affects several sections.** Since July, AI buyers have started cutting memory
content per unit because of price:
- NVIDIA halved SOCAMM per Vera CPU.
- Rubin Ultra's HBM has been cut, or is being tested at lower configurations.
- CSPs are evaluating 8-Hi rather than 12-Hi HBM for their ASICs.
- RDIMM capacity per server was cut in 1H26.

Under the model's definition (unrationed demand at constant 2025 prices), these are **rationing, not lower
demand**. They should not automatically lower the trend-content inputs. They do, however, contradict the
AGENTS.md statement that "AI/datacenter demand is never rationed in this model". The AI side is price
elastic at the margin too. This is the most important interpretive change since July.

---

## 1. Industry data since July 2026

### 1.1 DRAM revenue and prices

**F1.1 – 2Q26 DRAM industry revenue: US$154.73bn, +59.5% QoQ.** Bit shipments grew "only modestly".
Supplier shares: Samsung $60.98bn (39.4%), SK hynix $38.59bn (24.9%), Micron $36.0bn (23.3%), Nanya
$2.61bn, Winbond $1.0bn, PSMC $0.115bn. A secondary report puts CXMT at ~$14.6bn (+99% QoQ, ~9.5% share);
that figure is not on the TrendForce page.
- Source: [TrendForce press release](https://www.trendforce.com/presscenter/news/20260907-13219.html), 2026-09-07 (primary). CXMT figure: [10jqka](https://news.10jqka.com.cn/20260908/c679694511.shtml), 2026-09-08.
- Confidence: high (total); medium (CXMT).
- Key: `actuals.dram_industry_revenue_usd_bn[2026Q2]` = **152.3** (preliminary). **SUPPORTS**, within 1.6%. Replace with 154.73.
- Key: `actuals.dram_blended_asp_qoq[2026Q2]` = **0.55**. **SUPPORTS**. +59.5% revenue on "modest" bits implies a blended ASP rise of roughly +50–57%.
- Key: `actuals.dram_supply_eb_per_quarter[2026Q2]` = **10.8** (vs 10.0 in Q1, +8%). **MIXED**. Revenue ÷ ASP gives only about +1–6% bit growth. Check that the Q2 EB value is consistent with the revenue and ASP chain in the same file.

**F1.2 – 3Q26 DRAM prices and bits (company-reported; the TrendForce ranking is not yet out).**
- Samsung: DRAM ASP about +20% QoQ; DRAM bits up low-to-mid single digits; NAND ASP up high teens; NAND bits up mid single digits ([investing.com transcript](https://www.investing.com/news/transcripts/earnings-call-transcript-samsung-electronics-posts-record-q3-2026-profit-93CH-4981365), 2026-10-29; [VLSI Korea](https://www.vlsi.kr/en/samsung-q3-2026-earnings-11-facts-en/), 2026-10-29).
- SK hynix: DRAM bits about +10%; ASP up in the high 20s % ([StockHub call notes](https://stockhub.kr/en/insights/view_1793152574975_d6cb11f87d), 2026-10-28).
- TrendForce guided 3Q26 conventional DRAM contract prices +13–18% QoQ ([2026-09-07](https://www.trendforce.com/presscenter/news/20260907-13219.html)).
- **Derived estimate of 3Q26 DRAM industry revenue: about $190–210bn (+23% to +35% QoQ).** Blended ASP roughly +18% to +28%; bits roughly +3% to +10%.
- Confidence: medium (company data); low (the industry total is my derivation).
- Keys: a new 2026Q3 entry in `actuals.dram_industry_revenue_usd_bn`, `dram_blended_asp_qoq` (~0.20–0.25), and `dram_supply_eb_per_quarter` (~11.1–11.7 EB if 2026Q2 = 10.8). Only add these if `actuals_end` moves to 2026Q3. Better to wait for TrendForce's early-December ranking.

**F1.3 – 4Q26 price forecasts.**
- TrendForce: conventional DRAM contract **+10–15% QoQ**; NAND Flash **+15–20% QoQ**. Enterprise SSD is the only category accelerating. eSSD bit demand is forecast at **>+80% YoY in 2026**, and "most incremental supply has already been committed". Source: [TrendForce](https://www.trendforce.com/presscenter/news/20260930-13258.html), 2026-09-30 (primary).
- A later TrendForce News note puts DRAM contract prices (blended, apparently including HBM) at about **+20% QoQ** in 4Q26. Its "roughly 80% in 2Q, 40% in 3Q" comparison does not match the 13–18% guide for 3Q, so it is probably a different basket. Source: [TrendForce News](https://www.trendforce.com/news/2026/10/20/news-dram-prices-seen-rising-20-qoq-in-4q26-despite-slower-gains-ai-demand-tight-supply-support-outlook/), 2026-10-20.
- Range: **+10% to +20% QoQ** for DRAM in 4Q26. Gains are decelerating each quarter (2Q about +58–63%, 3Q +13–18% conventional, 4Q +10–15%).
- Confidence: high (direction); medium (exact numbers).
- Keys: no direct key, because the model has no price layer. Relevant to the `market.py` stub and to the narrative that the price peak is decelerating. For 4Q26 bits: Samsung guided DRAM bits **+mid-to-high teens % QoQ** and NAND **+mid teens**. SK hynix guided DRAM bits **+mid 20s %** (M15X, 1c, HBM4). A large 4Q bit jump is coming, partly from new capacity. This bears on the first projected quarters of `dram_supply`.

**F1.4 – Spot market.** DDR5 spot is still rising: 16Gb DDR5 went from $54.25 to $61.50 between Sep 2 and Oct 30. DDR4 spot is about 11% off its early-September peak and is "trading subdued". Sources: [TrendForce spot update](https://www.trendforce.com/news/2026-10-21/insights-memory-spot-price-update-ddr5-supply-tight-ddr4-trading-subdued-despite-0-84-gain-in-mainstream-prices), 2026-10-21; DRAMeXchange via secondary, 2026-10-30. A secondary site claims NAND contract prices stopped rising in October for the first time in 21 months ([tech-insider](https://tech-insider.org/dram-record-high-nand-flat-21-months-october-2026/), low confidence).
- Confidence: medium.
- Keys: none directly. This is an early-warning signal for `inventory_swing`: legacy and consumer channels are softening first.

**F1.5 – Inventory.** Supplier DRAM inventories are at "historic lows" across server and consumer segments. CSPs are buying extra server DRAM to build buffers ahead of a tighter 2027. PC OEMs are relying on inventory built in 1H26. Smartphone brands are "mostly relying on existing inventory", and IDC warns of a phone inventory build heading into 2027. Sources: [TrendForce Server DRAM 3Q26](https://www.trendforce.com/research/download/RP260909GQ), 2026-09-09; [TrendForce bulletin](https://www.trendforce.com/research/download/RP260929DY), 2026-09-30; [TrendForce 4Q26 price PR](https://www.trendforce.com/presscenter/news/20260930-13258.html); [IDC via FoneArena](https://www.fonearena.com/blog/495163/global-smartphone-shipments-q3-2026-idc.html), 2026-10.
- Confidence: medium.
- Key: `demand_conventional.inventory_swing.dram_eb_per_year` = {2026: **+1.5**, 2027: **+1.0**, 2028+: 0}. **MIXED**. CSP restocking supports a positive 2026. Consumer OEMs are already drawing down 1H26 stock, and IDC flags a 2027 channel build in phones. The 2027 value of +1.0 is the most exposed: a split of CSP restock plus consumer destock could net to about zero or below. Same logic for `nand_eb_per_year` (2026 +30, 2027 +20), where client-SSD OEMs are drawing down inventory.

**F1.6 – 2027 DRAM supply and demand framing.**
- SK hynix CEO (2026-07-21): 2027 industry **wafer supply +12%**, about half of the growth consumed by HBM. **Ex-HBM DRAM bit growth about 15%** against **demand +22%**, both for 2027–28. Calls 2027 "the worst year in the industry's history from the supply perspective." Source: [Wccftech](https://wccftech.com/sk%2Dhynix-ceo-rings-alarm-bells-next-year-will-be-the-worst-year-in-the-industrys-history-from-the-supply-perspective/), 2026-07-21.
- SK hynix Q3 call: 2027 achievable demand growth **mid-20s % for DRAM**, **high teens for NAND**. DRAM and HBM effectively sold out through 2029 including LTAs; constraints expected through 2030. Source: [StockHub](https://stockhub.kr/en/insights/view_1793152574975_d6cb11f87d), 2026-10-28.
- Samsung Q3 call: tight supply into 2028. A large 2027 capex increase is coming, but much of it is cleanroom shells, so it "will be hard to add bit output in 2028". Sources: Samsung transcript and VLSI Korea, 2026-10-29.
- TrendForce: server DRAM plus HBM bit supply **+27% in 2027**. HBM plus RDIMM were 51% of DRAM bits in 2026. RDIMM bit supply +15–20% in 2027. "Meaningful bit output" from new fabs arrives only in **2H27**. Sources: [TrendForce](https://www.trendforce.com/presscenter/news/20260825-13198.html), 2026-08-25; [TrendForce outlook report summary](https://www.trendforce.com/research/download/RP260929AN), 2026-10-01.
- Confidence: medium.
- Keys: `supply_capacity.dram_wafer_capacity_kwspm` totals. The model's global total goes from 2,242 in 2026 to about 2,470 in 2027 (+10%; ex-China +8%). **SUPPORTS** the ~12% wafer growth within range. 2027 DRAM bit supply growth of roughly 13–18% overall is the external benchmark to check the model's 2027 supply line against.

### 1.2 HBM

**F1.7 – HBM share of DRAM wafers and bits.** TrendForce: "HBM wafer input among the top three suppliers will account for approximately 18%, 22%, and 30% of total DRAM wafer input" (2025/26/27). HBM bits are about 8%, 9% and 13% of total DRAM bits. Source: [TrendForce](https://www.trendforce.com/presscenter/news/20260602-13074.html), 2026-06-02 (primary; just before the July update, but the 2027 number was not in the model). Samsung's EVP said HBM will take "nearly 30% of industry DRAM capacity in 2027, up from ~20% now". Source: [TrendForce News citing Reuters](https://www.trendforce.com/news/2026/09/29/news-samsung-sees-hbm-taking-nearly-30-of-industry-dram-capacity-in-2027-up-from-20-currently/), 2026-09-29.
- Confidence: medium. **The denominator is ambiguous**: "total DRAM wafer input" could mean the top three's own wafers or the industry.
- Key: `tech_roadmap.hbm_wafer_share` (ex-China denominator) = {2026: **0.261**, 2027: **0.339**, 2028: 0.398}.
  - If the 22%/30% figures already use a top-three denominator, the model's /0.844 conversion double-counts: 2026 should be ~0.22 and 2027 ~0.30. The model is **high by ~4 points**.
  - If the denominator is the industry, 2027 = 0.30/0.83 ≈ **0.36**, and the model is slightly low.
  - **Range for 2027: 0.30–0.37.** Verdict MIXED. The model's 2027 value sits inside the range, but the 2026 conversion should be re-checked.

**F1.8 – Trade ratio implied by TrendForce's own wafer and bit shares.** Solving the model's formula with 2027 = 30% of wafers and 13% of bits gives **k ≈ 2.87**. With 2026 = 22%/9%, k ≈ 2.85. A Chinese industry source says one HBM die uses about the wafer area of 3GB of DDR5, i.e. HBM uses about 3x the area ([TrendForce News](https://www.trendforce.com/news/2026/09/29/news-samsung-sees-hbm-taking-nearly-30-of-industry-dram-capacity-in-2027-up-from-20-currently/), citing ijiwei).
- Confidence: medium.
- Key: `tech_roadmap.hbm_trade_ratio` = {2026: **2.85**, 2027: **3.05**, 2028: 3.15 … 2032: 3.3}. 2026 **SUPPORTS**. 2027 **CONTRADICTS mildly**: TrendForce's numbers imply a flat ~2.85–2.9, not 3.05.
- Pushing the other way: Samsung said HBM4E and HBM5 have larger die sizes and more metal layers (a "physical constraint on supply").
- Pushing back down: the move to 8-Hi stacks in 2027 (F3.3) improves stack yield, which lowers wafers per good bit.
- Suggest 2027 ≈ 2.9 with the later path flattened.

**F1.9 – HBM bit growth and supplier volumes.**
- TrendForce: 2027 HBM bit shipments **+50–60% YoY**, still short of demand ([2026-08-04](https://www.trendforce.com/presscenter/news/20260804-13166.html), primary); about +43% in 2028 (secondary).
- Reported supplier volumes (CEO remarks via [Wccftech](https://wccftech.com/sk%2Dhynix-ceo-rings-alarm-bells-next-year-will-be-the-worst-year-in-the-industrys-history-from-the-supply-perspective/), 2026-07-21; units read as billion Gb). Samsung goes from about **12bn Gb (1.5 EB) in 2026 to 20bn Gb (2.5 EB) in 2027**. SK hynix goes from about **18bn Gb (2.25 EB) to 24bn Gb (3.0 EB)**. Adding Micron gives an industry total of roughly **4.5–5 EB in 2026** and **~7 EB in 2027**.
- UBS 2027 HBM demand is **58bn Gb (7.25 EB)** (raised from 53.9). JPMorgan's 2026–28 cumulative is **163bn Gb (20.4 EB)**, a 63% CAGR (secondary, [itiger](https://www.itiger.com/news/1175901853)).
- Samsung's HBM wafer input goes from about **180k/month (2026) to 250k/month (2027)**, +39% ([Seoul Economic Daily via TrendForce](https://www.trendforce.com/news/2026/09/29/news-samsung-sees-hbm-taking-nearly-30-of-industry-dram-capacity-in-2027-up-from-20-currently/), 2026-09-20).
- Confidence: medium.
- Key: `constraints.hbm_backend.max_hbm_bits_eb_per_year` = {2026: **5.2**, 2027: **7.5**, 2028: **10.5**}. Key: `constraints.test.max_hbm_bits_eb_per_year` = {2026: **5.0**, 2027: **7.0**, 2028: **9.8**}. **SUPPORTS**: the ceilings sit just above the reported 2026–27 supply. Note that TrendForce's +43% for 2028 puts 2028 HBM supply at about 10 EB, right at the C4 and C5 ceilings, so the back-end could bind in 2028. Worth watching.

**F1.10 – HBM pricing (context for the price stub).** TrendForce raised 2027 blended HBM ASP to **+121% YoY**. 8-Hi carries a 10–20% per-Gb premium over 12-Hi. Its earlier range for contract prices was +70–140%. Samsung has reportedly asked for more than double on HBM4 for 2027. Samsung says 2027 HBM is "sold out at agreed target prices". Sources: [TrendForce](https://www.trendforce.com/presscenter/news/20260929-13255.html), 2026-09-29 (primary); [TrendForce](https://www.trendforce.com/presscenter/news/20260825-13198.html), 2026-08-25.
- Confidence: high.
- Key: none (no price layer). It explains F3.3: vendors are cutting HBM GB per unit because HBM costs have doubled.

### 1.3 NAND

**F1.11 – 2Q26 NAND revenue.** The top five reached **$68.87bn (+77% QoQ)**: Samsung $23.06bn, SK hynix Group $14.27bn, Micron $11.85bn, Kioxia $10.72bn, SanDisk $8.97bn. Source: [TrendForce](https://www.trendforce.com/presscenter/news/20260818-13186.html), 2026-08-18 (primary). The top five **enterprise SSD** vendors reached **$37.59bn (+103.6% QoQ)**, i.e. eSSD is now more than half of NAND revenue. Source: [TrendForce via I-Connect007](https://iconnect007.com/article/151415/top-five-enterprise-ssd-vendors-revenue-nears-3759b-in-2q26/151412/), 2026-09-01.
- Confidence: high.
- Key: `actuals.nand_supply_eb_per_quarter` (2026Q2 = **395**). The revenue chain can be re-derived. The more important point is the next finding.

**F1.12 – NAND was in deficit all of 2026, and eSSD demand is exploding.** TrendForce estimates a 2026 supply deficit of **4–5%**, easing in **2H27** as new capacity arrives. Servers are **>40% of NAND bit demand**; smartphones and notebooks together are about 40%. eSSD bit demand is **>+80% in 2026**. Kioxia sees NAND bit demand growth of **high teens in CY26** and **low 20s % in CY27**, with data centers offsetting consumer weakness and strong growth continuing into CY28, and it has started site prep for Kitakami K3. Samsung is shipping a 256TB QLC eSSD (V9 2Tb QLC) in early 2027 and cites agentic AI and KV cache as drivers. Seagate nearline HDD exabytes are reportedly allocated into 2028.
- Sources: [Blocks & Files](https://www.blocksandfiles.com/flash/2026/07/24/where-did-that-nand-upstart-come-from/5278261), 2026-07-24; [TrendForce 4Q26 PR](https://www.trendforce.com/presscenter/news/20260930-13258.html), 2026-09-30; Kioxia call via [roic.ai](https://www.roic.ai/quote/TSE-285A/transcripts/2027-year/2-quarter), late Oct 2026; Samsung call 2026-10-29; Seagate via secondary (low confidence).
- Confidence: medium-high.
- Keys:
  - `demand_ai.nand_tb_per_accelerator` = {2026: **10.0**, 2027: **12.5**}.
  - `demand_conventional.servers_traditional.nand_tb_per_unit` = {2026: **29**, 2028: 42}.
  - **CONTRADICTS the model's NAND output.** The July review found the model shows NAND balanced to slight surplus in 2026, while reality shows a 4–5% deficit and eSSD bits up >80%. This confirms the July gap note: the model needs the HDD→QLC substitution segment, or higher AI and server NAND content, before its NAND line can be trusted.

**F1.13 – NAND capex lags.** "Cleanroom space limits and capital priority for DRAM keep NAND investment growth well behind revenue growth"; NAND bit growth relies mainly on node migration. Source: [TrendForce report summary](https://www.trendforce.com/research/download/RP260929AN), 2026-10-01.
- Confidence: medium.
- Key: `supply_capacity.nand_wafer_capacity_kwspm` (non-China producers). **SUPPORTS** slow capacity growth, and supports the July "DRAM pulls NAND capacity across" gap note.

### 1.4 Samsung Q3 2026 (primary source: earnings call 2026-10-29)

- Revenue KRW 195.25T; operating profit KRW 107.44T. DS: revenue KRW 147.1T, operating profit KRW 106.5T. Memory revenue KRW 140.7T (+16% QoQ).
- HBM4 revenue more than tripled QoQ and is now **60% of HBM sales**. Samsung's HBM share has reached parity with its DRAM share, earlier than its 2H target.
- **HBM4E mass production in 1H27**, volume ramp in 2H27. 2027 HBM is sold out, and customers are asking for more.
- 10 multi-year LTAs signed and 10 more in negotiation. Samsung targets 60–70% of capacity under LTAs through 2030.
- **DS capex 2026: KRW 76.8T** (+29.3T YoY). 2027 capex up substantially, but tilted to cleanroom shells. Samsung expects "some demand adjustment" in mobile and PC in 2027 and smartphone units to decline.
- Sources: [investing.com transcript](https://www.investing.com/news/transcripts/earnings-call-transcript-samsung-electronics-posts-record-q3-2026-profit-93CH-4981365); [VLSI Korea](https://www.vlsi.kr/en/samsung-q3-2026-earnings-11-facts-en/). Confidence: high.
- Keys: `supply_capacity.dram_wafer_capacity_kwspm.samsung` (see F4.1); `demand_conventional.smartphone.units_millions` (see F5.1).

### 1.5 CXMT and YMTC

**F1.14 – CXMT.**
- Listed on the Shanghai STAR market in late July 2026, raising about CNY 57.9bn.
- Capacity estimates: **300–350k wpm at end-2026**; Counterpoint gives **320–420k by 2027**; the company's ambition is **500k by 2028**.
- Revenue share about 9.5% in 2Q26 (secondary).
- DDR5 cost per bit is more than 30% above the big three.
- **HBM3**: samples shipped, mass production targeted for late 2026, 8-high yield reportedly about 25%. SemiAnalysis projects CXMT HBM wafer starts of **55k/month in 2027 and 100k in 2028**. Note the IPO prospectus reportedly contains no HBM project.
- 4F² design: about 33% cell-area reduction; commercialization after 2028.
- Sources: [Tom's Hardware](https://www.tomshardware.com/tech-industry/cxmt-closes-up-466-percent-in-shanghai-debut-with-no-hbm-project-in-its-ipo-prospectus), Jul 2026; [Counterpoint](https://counterpointresearch.com/mailto%3Apress%40counterpointresearch.com/insights/cxmt-stock-market-big-three-memory-club); [StartupFortune](https://startupfortune.com/chinas-cxmt-lists-on-july-27-in-asias-biggest-ipo-of-2026-and-its-already-moving-markets/), 2026-07-24; [TrendForce News](https://www.trendforce.com/news/2026/10/20/news-dram-prices-seen-rising-20-qoq-in-4q26-despite-slower-gains-ai-demand-tight-supply-support-outlook/), 2026-10-20.
- Confidence: medium (capacity); low (HBM).
- Keys:
  - `supply_capacity.dram_wafer_capacity_kwspm.cxmt` = {2026: **350**, 2027: **420**, 2028: **500**}. **SUPPORTS**; 2027 is at the top of Counterpoint's range.
  - `tech_roadmap.hbm_wafer_share` notes ("CXMT makes no HBM"). **CONTRADICTS from 2027.** At 55–100k HBM wafer starts in 2027–28, CXMT's HBM is no longer zero. It is captive to China, so global-gap invariance holds, but the ex-China denominator logic needs a China-HBM term.
  - `cxmt_density_discount` (2026: 0.66). A revenue share (~9.5%) below its wafer share (~13–15%) is consistent with the discount. **SUPPORTS.**

**F1.15 – YMTC.** Runs **two fabs at about 200k wpm combined** (Reuters, Apr 2026). The third Wuhan fab reaches **50k wpm by 2027**; plans total about 400–500k. YMTC had **~13–14% of NAND bits** in 1Q–2Q26 (third by bits per Counterpoint), and Chinese suppliers are heading to about **19% of global NAND bit output**. Sources: [Evertiq](https://evertiq.com/design/2026-04-14-ymtc-plans-new-fabs-to-boost-capacity-amid-rising-us-china-tensions), 2026-04-14; [digitalcitizen/Counterpoint](https://www.digitalcitizen.life/ymtc-becomes-worlds-third-largest-nand-supplier-with-14-percent-market-share/); [Blocks & Files](https://www.blocksandfiles.com/flash/2026/07/24/where-did-that-nand-upstart-come-from/5278261), 2026-07-24.
- Confidence: medium.
- Key: `supply_capacity.nand_wafer_capacity_kwspm.ymtc` = {2025: **130**, 2026: **155**, 2028: **200**, 2030: **240**}. **CONTRADICTS.** The model gives YMTC about 10% of NAND wafers. Observed is about 200k wpm already and 13–14% of bits. Suggest 2026 ≈ 200–210, 2027 ≈ 250, 2028 ≈ 300, 2030 ≈ 400. This is captive, so the global gap is invariant, but the ROW/China split and the NAND supply level both move.

---

## 2. Datacenter and AI demand

### 2.1 Hyperscaler capex (Q3 2026 earnings round, late October)

| Company | Latest 2026 capex guide | 2027 signal | Source, date |
|---|---|---|---|
| Alphabet | **$195–205bn** (raised from $180–190bn) | "significant increase"; one unconfirmed report says >$300bn | [Quartr](https://quartr.com/events/alphabet-goog-q3-2026_3ebmqmdr), [aiweekly](https://aiweekly.co/alerts/alphabet-posts-1276b-q3-with-google-cloud-up-103-to-307b-as-2027-capex-set-to), 2026-10-28 |
| Amazon | **~$220bn** (Q3 cash capex $75.9bn) | "meaningfully more" in 2027; AWS growth >40% in 2027 and 2028; backlog $578bn; Trainium sold externally from late 2027 | [The Stack](https://www.thestack.technology/from-bedrock-to-duckdb-to-leo-7-key-takeaways-from-amazons-earnings/), [Constellation](https://www.constellationr.com/insights/news/aws-q3-revenue-growth-surges-39-capex-stings-amazons-cash-flow), 2026-10-29 |
| Microsoft | about **$170bn** (sources disagree whether this is CY26 or FY27); Q3 (Sep) quarter $45.2bn, Dec quarter >$50bn | capacity-constrained; some third-party capacity slipped into 2H FY27 | [Analytics India Mag](https://analyticsindiamag.com/ai-news/microsofts-azure-revenue-grows-48-in-september-quarter), [InvestingLive](https://investinglive.com/stocks/microsoft-sees-170bn-capex-in-fiscal-2027-but-says-it-will-stay-cash-flow-positive/), 2026-10-28 |
| Meta | **$135–145bn** (floor raised); Q3 $34.9bn, above operating cash flow | no number; "continue investing aggressively"; $825bn of lease and contract commitments | [Meta 8-K](https://www.sec.gov/Archives/edgar/data/0001326801/000162828026066700/meta-09302026xexhibit991.htm), 2026-10-21 |
| Oracle | FY27 (to May 2027) **$90–95bn** gross, ~$70bn net cash | RPO $664bn; delivered **850 MW** and 300k GPUs in a single quarter | [DCD](https://www.datacenterdynamics.com/en/news/oracle-delivered-300000-gpus-in-q1-fy2027/), [beancount](https://beancount.io/blog/2026/09/13/oracle-fy2027-q1-earnings-analysis), 2026-09 |

- The big four plus Oracle come to roughly **$820–860bn** for 2026.
- **TrendForce, nine CSPs** (the five above minus Oracle's overlap, plus ByteDance, Tencent, Alibaba, Baidu): **$957bn in 2026 (+106%)** and **>$1.5tn in 2027 (+60%, revised up from +50%)**. The revision is driven by "rising prices for complete server systems, higher component quotations amid supply shortages, and advance payments". AI server revenue goes from about $479bn (2026) to about **$920bn (2027, +90%)**; AI server units grow +32% in 2026 and **+36% in 2027**. Source: [TrendForce via I-Connect007](https://iconnect007.com/article/151981/csp-capex-to-exceed-us15t-in-2027-as-ai-server-revenue-surges/151978/smt), 2026-10-14.
- TrendForce also says DRAM plus NAND will be **47% of major CSP capex in 2026 and 68% in 2027** ([TrendForce](https://www.trendforce.com/presscenter/news/20260825-13198.html), 2026-08-25, primary; the definition is not given and may be hardware rather than total capex).
- Goldman projects about $1.14tn of 2027 hyperscaler capex (Sept 2026, secondary).
- Confidence: high (company guides); medium (TrendForce totals).

**Bearing on keys:**
- `demand_ai.hyperscaler_capex_usd_bn` = {2026: **620**, 2027: **850**, 2028: 1,100}. **CONTRADICTS (too low in nominal dollars).** Observed 2026 is roughly **$850–960bn** even before xAI, OpenAI's own spend, CoreWeave and neoclouds. TrendForce's 2027 figure is >$1.5tn.
  - **Important caveat for how to update.** A large part of the overshoot is memory and component *price inflation*. 2027 CSP capex is +60% while AI server *units* are only +36%. The model's demand is at constant 2025 prices.
  - If capex is raised in nominal terms, `avg_accelerator_asp_usd` (2026: **15,500**, 2027: **16,500**) must also be raised. Otherwise `desired_units = capex/ASP` overstates units.
  - Cleaner option: deflate capex to 2025 dollars. Using TrendForce's unit growth (+32% 2026, +36% 2027) as the real-volume anchor gives about **$560bn (2026)** and **~$760bn (2027)** in 2025 dollars, close to the current values.
  - **Verdict: the nominal series is badly stale; in real terms it is roughly right.** Document which convention the cross-check uses.
- `demand_ai.accelerator_share_of_capex` = {2026: **0.45**, 2028: 0.44}. **MIXED.** If memory is 47–68% of capex (partly as HBM inside accelerator prices), the "accelerator" share's definition gets blurry. Low confidence either way.

**F2.2 – NVIDIA.**
- Q2 FY27 (quarter ended 2026-07-26): revenue **$96.2bn**; Data Center **$89.0bn (+117% YoY, +18% QoQ)**.
- Vera Rubin is in full production, expected at about 20% of DC revenue in FQ3.
- FQ3 guide: **$108bn ±2%**. Zero China DC compute assumed. Supply and capacity commitments **$279bn**.
- **FY2028 (Feb 2027–Jan 2028) revenue growth preliminarily about +70%.** Supply constraints expected through at least FY2028.
- $1tn of Blackwell plus Rubin demand visibility through CY2027 (GTC, March 2026).
- Sources: [Pulse 2.0](https://pulse2.com/nvidia-operating-income-jumps-124-to-63-7-billion-as-revenue-doubles-and-q3-outlook-hits-108-billion/), 2026-08-26; [Quartr](https://quartr.com/events/nvidia-corporation-nvda-q2-2027_33dRoFp6); [DCD](https://www.datacenterdynamics.com/en/news/nvidia-ceo-jensen-huang-says-company-has-one-trillion-dollars-in-orders-through-2027).
- Confidence: high.
- Key: `actuals.accelerator_units_millions_per_quarter[2026Q2]` = **4.5**. **SUPPORTS.** DC revenue +18% QoQ is consistent with the Q1-anchored path; Q3 calendar is tracking about +10–15% QoQ in dollars, with fewer units than dollars as the Rubin ASP rises. The FY28 +70% guide says **2027 accelerator dollars about +60–70%**, above the model's capex path (see F2.1).

**F2.3 – Broadcom and AMD.**
- Broadcom FQ3 (to Jul 31): AI revenue **$16.7bn (+221%)**; FY26 AI about $58bn; **FY27 about $115bn (supply secured)**; line of sight to **~$230bn in FY28**. Anthropic is to be its largest XPU customer in 2027. OpenAI is to deploy **>5 GW** of "Jalapeno"-generation XPUs in 2028. Source: [TIKR](https://www.tikr.com/blog/google-anthropic-and-openai-just-locked-in-broadcoms-q3-earnings-through-2028), [cryptobriefing](https://cryptobriefing.com/broadcom-ai-chip-revenue-grows-221-percent/), early Sep 2026.
- AMD Q3 (reported 2026-11-04): first MI455X/Helios revenue; Q4 guide about $17bn; AI GPU about $7bn in Q4 (broker estimate); management talks of >80% revenue growth in 2027. Source: [InvestingLive](https://investinglive.com/stocks/amd-shares-rise-after-hours-as-q4-revenue-outlook-of-17bn-tops-forecasts-on-ai-ramp/), [36kr](https://eu.36kr.com/en/p/4054858988344195), 2026-11-04.
- Confidence: medium-high.
- Key: `demand_ai.hyperscaler_capex_usd_bn` and the accelerator mix. **SUPPORTS strong 2027–28 unit growth**, and an ASIC share that keeps rising.

### 2.2 Power and GW pipeline

**F2.4 – US delivered vs announced.**
- Goldman: realized US data-center additions were **6.4 GW (2024)** and **8.5 GW (2025)**. Scheduled additions are **13.6 GW (2026)** and **36.3 GW (2027)**. About 60% of next-year scheduled capacity materializes on time, falling to about 50% two years out. They still see 2.2 GW realized in 1Q26 plus 11.5 GW over the rest of 2026. Source: [Goldman Sachs](https://www.goldmansachs.com/insights/articles/us-data-center-power-demand-projected-to-double-by-2027), via secondary; date not confirmed (2026).
- Sightline/Bloomberg: **16 GW announced for 2026 across 140 US projects, of which only about 5 GW is under construction**; **21.5 GW announced for 2027, of which 6.3 GW has broken ground**; 30–50% of 2026 capacity is delayed or cancelled; 9 cancellations in the 2026 dataset. Source: [tech-insider compilation](https://tech-insider.org/us-ai-data-center-delays-cancellations-7gw-capacity-crisis-2026/), updated to 2026-11-05 (secondary).
- Interconnection waits of 4–7 years in NoVA, Phoenix and Dallas. The ERCOT large-load queue went from 63 to 226 GW in a year. Gas turbine orders rose 70% in 2025. Source: [9to5ai](https://9to5ai.tech/the-gigawatt-datacenter-race), 2026-10-20.
- Oracle alone delivered **850 MW in one quarter** (F2.1).
- Confidence: medium.
- Keys:
  - `datacenter.realisation_rate` = {2026: **0.62**, 2027: **0.52**, 2028: **0.47**}. **SUPPORTS** (Goldman's 60%, then 50%). Sightline's under-construction ratios (~31% for 2026, ~29% for 2027) argue for the low side.
  - `datacenter.announced_gw_per_year` = {2026: **32**, 2027: **46**} (global). **MIXED.** A US 2027 schedule of 36 GW (Goldman) implies global announced well above 46 for 2027. Sightline's 21.5 GW US figure fits better with the model.
  - Delivered: the model calibrates to about **25 GW delivered in 2026**. US realized is about 13–14 GW for all data centers, not only AI. Global AI-specific delivered is probably **~15–22 GW**. **CONTRADICTS mildly (model may be high in 2026)**, but 2026 is mostly pinned by actuals for units, so the effect is on fleet state and power eviction.
  - `datacenter.grid_interconnect_gw_ceiling` = {2026: 35, 2027: 45}. **SUPPORTS** a non-binding ceiling in 2026; the constraint shows up as slip.

**F2.5 – OpenAI and Stargate.** No new program total since "over 8 GW" (Oct 2025). Abilene (1.2 GW) is partly operating; reports range from 2 of 8 buildings (June) to about 618 MW (September). Stargate UAE's first 200 MW was unverified as of mid-October. Reported OpenAI compute spend through 2030 is about $750bn (up from about $600bn). NVIDIA said its $30bn OpenAI investment "might be the last", and the $100bn / 10 GW plan is "probably not in the cards" (2026-03-04). Sources: [9to5ai](https://9to5ai.tech/the-gigawatt-datacenter-race), 2026-10-20; [stargate.how](https://stargate.how/location), 2026-10-18; [PC Gamer](https://www.pcgamer.com/software/ai/nvidias-jensen-huang-i-think-the-opportunity-to-invest-usd100-billion-in-openai-is-probably-not-in-the-cards).
- Confidence: medium-low.
- Key: `datacenter.slip_quarters` = **3**. **SUPPORTS** (Abilene and UAE slipping by quarters, not cancelled). `cancellation_asymmetry` = **0.15**: no evidence to move it.

### 2.3 Signs of slowing or accelerating

**F2.6 – Credit stress at neoclouds.** CoreWeave CDS spreads widened sharply (+1,200bp is cited) and neocloud stocks slid in mid-October. Meta's Q3 capex exceeded its operating cash flow; Alphabet, Amazon and Microsoft FCF are compressing. Gartner does not expect AI revenue to catch up with DC capex until 2032–33. Dan Ives: Big Tech capex *growth rate* peaks in 2027. Sources: [roic.ai](https://www.roic.ai/news/ai-neocloud-stocks-slide-as-financing-fears-mount-10-15-2026), 2026-10-15; [Fierce](https://www.fierce-network.com/cloud/wall-streets-anxiety-catches-neocloud-coreweave); [TIKR/Ives](https://www.tikr.com/blog/dan-ives-big-tech-free-cash-flow-will-trough-in-1h2027-as-capex-growth-peaks-early), 2026-11-05.
- Confidence: medium.
- Key: `uncertainty.yaml` correlation cluster and the July gap note ("macro / financing cycle"). **SUPPORTS keeping a fat left tail** on capex and realisation from 2028. No 2027 guide has been cut yet; every hyperscaler raised or held.

**F2.7 – Token demand is far above the KV sub-model's scale.** Google processed **>3.2 quadrillion tokens/month in May 2026**, up from about 480T a year earlier. Its API is at about 32bn tokens/minute (about 1.4 quadrillion/month), **+40% QoQ** and more than 4x YoY (Q3 call, 2026-10-28). OpenRouter's run-rate is about 10 quadrillion/yr (Oct 2026). NVIDIA claims Rubin delivers about 10x lower cost per token than Blackwell. Sources: [Shacknews](https://www.shacknews.com/article/149205/google-3-2-quadrillion-monthly-ai-tokens), May 2026; [ppc.land](https://ppc.land/gemini-app-gains-350m-users-in-a-year-to-pass-1bn-alphabet-says/), 2026-10-28; [cryptobriefing](https://cryptobriefing.com/openrouter-10-quadrillion-token-run-rate/), Oct 2026.
- Confidence: medium-high (Google figures are company-stated).
- Keys:
  - `demand_ai.kv_cache.tokens_served_trillions` = {2026: **1,500**, 2027: 3,200}. **CONTRADICTS by more than an order of magnitude.** Google alone runs at about 38,000 trillion/yr. If this series feeds any bits, it is far too low; if it is only labelling, fix the label or the scale.
  - `demand_ai.efficiency_deflator_annual` = {2026: **0.12**, 2027: 0.10}. **MIXED.** Cost per token is collapsing (consistent with a high deflator), yet token volume grows 4–7x/yr, which is the Jevons rebound flagged in the July gap note. The evidence argues against treating the deflator as pure demand destruction.

---

## 3. Accelerator roadmaps and memory per unit

**F3.1 – NVIDIA Rubin (2026–27 volume part).** 288GB HBM4 per GPU (8 stacks × 36GB, 12-Hi). NVL72 has 20.7TB HBM4. Rubin keeps 12-Hi HBM4 per TrendForce. Production shipments began around August 2026, with a volume ramp in 4Q26 and 1H27. One KeyBanc/TrendForce item says Rubin's share of 2026 shipments was trimmed from 29% to 22% because of HBM4 qualification delays. Sources: [computing.co.uk](https://www.computing.co.uk/news-network/2026/nvidia-touts-new-storage-platform-confidential-computing-for-vera-rubin); [Wccftech](https://wccftech.com/nvidia-confirms-vera-rubin-launch-in-q3-volume-ramp-q4-blackwell-continues-to-see-massive-demand/); [SDxCentral](https://www.sdxcentral.com/news/nvidias-rubin-gpus-hit-the-brakes-as-hbm4-memory-drought-threatens-jensens-supply-chain-magic-report/).
- Confidence: high (spec); medium (mix).
- Key: `demand_ai.hbm_gb_per_accelerator` = {2026: **280**, 2027: **330**}. **SUPPORTS.** The 2026 blend is GB300 288 and Rubin 288, plus TPU 192–288, Trainium3 144, Maia 200 216, MI455X 432. 330 for 2027 is plausible, but only if ASIC content doesn't fall (F3.3).

**F3.2 – Rubin Ultra (late 2027) has been cut.** It was announced at GTC 2026 as 1TB HBM4E (four dies, 16 stacks of 16-Hi).
- Jun 2026: reportedly moved to **two dies, 8 stacks of 12-Hi HBM4E, ~384GB** (iM Securities 2026-06-18; Tom's Hardware/SemiAnalysis 2026-06-30). TrendForce's June PR also says 384GB per GPU.
- Aug 2026: TrendForce says NVIDIA is now testing **8-Hi HBM4E, 12-Hi HBM4 and 8-Hi HBM4**; final spec undecided; raising I/O speed is the priority over volume. SemiAnalysis and The Information report test versions with **192GB HBM4**.
- Sources: [TrendForce](https://www.trendforce.com/presscenter/news/20260804-13166.html), 2026-08-04 (primary); [Tom's Hardware](https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidia-reportedly-cancels-quad-die-rubin-ultra-gpu-in-favor-of-dual-gpu-design-report-claims-complex-design-purportedly-scrapped-over-manufacturing-execution-concerns), 2026-06-30; [TechNews](https://technews.tw/2026/08/11/nvidia-reportedly-testing-lower-memory-configs-of-rubin-ultra-as-memory-shortage-bites-back/), 2026-08-11.
- Range for the Rubin Ultra package: **192–384GB** (vs 1TB at GTC).
- Confidence: medium (NVIDIA has not confirmed).
- Keys:
  - `demand_ai.hbm_gb_per_accelerator` = {2028: **410**, 2029: 500, 2030: 610 … 2032: **880**}. **CONTRADICTS the slope**, at least through 2028. The flagship content that justified 410 by 2028 (Rubin Ultra ~1TB) is now 192–384GB per package.
  - Under the model's own definition, much of this cut is *price rationing* (TrendForce: "more GPUs from the same HBM bit output"). An honest update would keep unrationed trend content modestly above shipped content: for example 2028 ≈ 360–380 rather than 410, with a flatter path afterwards.
  - The model notes in `demand_ai.yaml` and `gpu_fleet.yaml` ("Rubin Ultra ~1TB") are now stale.
  - Also `constraints.advanced_packaging.accelerators_per_cowos_wafer` (2028: **20**): a two-die package is smaller than four-die, so the falling path may be too steep. Low confidence.

**F3.3 – ASICs moving to 8-Hi and lower HBM capacity.** TrendForce reports that several CSPs are evaluating lower HBM capacity for next-gen ASICs, with **8-Hi a priority evaluation for 2027**. 8-Hi lowers stack cost and supports "more GPUs from the same HBM bit output". Sources: [TrendForce](https://www.trendforce.com/presscenter/news/20260929-13255.html), 2026-09-29; [TrendForce](https://www.trendforce.com/presscenter/news/20260804-13166.html), 2026-08-04 (both primary). Current ASIC content: TPU 8i 288GB HBM3E; Trainium3 144GB HBM3E; Maia 200 216GB HBM3E; MTIA 500 up to 512GB (H2 2027); MI455X 432GB HBM4.
- Confidence: medium.
- Key: `demand_ai.hbm_gb_per_accelerator[2027]` = **330**. **MIXED.** Realized blended 2027 content is likely **~290–330**. Unrationed content can stay near 330. Flag this in the notes.

**F3.4 – Host DRAM per accelerator (SOCAMM/LPDDR).** NVIDIA **halved SOCAMM capacity** on Vera Rubin superchips (TrendForce PR, 2026-06-10). The reported per-rack LPDDR5X fell from about 55TB to 28TB, i.e. about 750GB/GPU to about 380GB/GPU (secondary). NVIDIA's public spec still says up to 1.5TB per Vera CPU. The big three's initial 2027 LPDDR allocations cover only **~60% of NVIDIA's estimated need**. TrendForce expects AI servers to become the **largest LPDRAM end-market between 2028 and 2030**. CSPs and OEMs also cut RDIMM capacities in 1H26. Sources: [TrendForce](https://www.trendforce.com/presscenter/news/20260610-13090.html), 2026-06-10 (primary); [TrendForce](https://www.trendforce.com/presscenter/news/20260804-13166.html), 2026-08-04.
- Confidence: medium.
- Key: `demand_ai.conventional_dram_gb_per_accelerator` = {2026: **175**, 2027: **200**, 2030: 290}.
  - **MIXED, leaning CONTRADICTS (too low for unrationed demand).** NVIDIA's flagship host memory is about 380–750GB per GPU. Even blended with ASICs that carry far less host memory, 175–200 looks low as *trend* content.
  - The 60% LPDDR coverage is direct evidence that this segment is rationed in 2027, which again contradicts "AI is never rationed".
  - Suggest raising unrationed 2027 to about 250–300 (low confidence), and checking it against the server-CPU finding (F5.3) to avoid double counting.

**F3.5 – GPU timing (supports the model's annual cadence).**
- Rubin volume 4Q26 to 1H27.
- Rubin Ultra late 2027, contributing from about 4Q27.
- Feynman 2028.
- AMD MI455X shipping from 3Q26, ramping 4Q26; MI500 (HBM4E, CDNA 6) 2027; MI600 2028.
- TPU v8 (8t Broadcom, 8i MediaTek) late 2027.
- Trainium3 since early 2026; Trainium4 about 18 months out (~late 2027); Trainium sold externally from late 2027.
- MTIA 450 1H27, MTIA 500 end-2027.

Sources: see F2.3 and [hothardware](https://hothardware.com/news/instinct-mi400-challenge-vera-rubin), [aiweekly](https://aiweekly.co/alerts/meta-sets-mtia-450-for-h1-2027-data-center-deployment-mtia-500-by-end-of-year). TPU unit forecasts for 2027 range from **5M** (Morgan Stanley) to **8.8M** (GF Securities). ASIC shipments are forecast **+44.6% in 2026 vs GPUs +16.1%** (TrendForce via secondary). ASIC-based servers were 27.8% of AI servers in 2026 and are rising in 2027.
- Confidence: medium.
- Keys: `gpu_fleet.vintages` kw_per_unit and tflops_per_watt (2027: 1.20 kW, 20 TFLOP/W). **SUPPORTS.** The ASIC mix keeps blended kW below flagship.

**F3.6 – HBM4 and HBM4E qualification and timing.**
- **Samsung**: HBM4 (1c-based) first mass shipments February 2026; qualified at 10–11 Gbps for Rubin; HBM share now at parity with its DRAM share; HBM4E mass production 1H27.
- **SK hynix**: about 60–70% of NVIDIA's HBM4; HBM4 overtakes HBM3E in 4Q26; uses 1b for HBM4 and 1c for HBM4E. Reports of 16-Hi 48GB volume in 3Q26 are unreliable.
- **Micron**: shipped >$1bn of HBM4, but reportedly lower yield and capacity. One report says it is relegated to mid-tier parts such as Rubin CPX; Micron disputes this.
- **Hybrid bonding** is pushed to HBM4E/HBM5 (2027 and later); yields reportedly about 10% vs a 60% threshold for commercial use. SK hynix keeps MR-MUF for 16-Hi.
- Sources: [TrendForce News](https://www.trendforce.com/news/2026/03/09/news-samsung-sk%E2%80%AFhynix-reportedly-tapped-as-nvidia-rubin-hbm4-suppliers-shipments-could-start-in-march), [JoongAng](https://www.koreajoongangdaily.com/business/sk%2Dhynix-has-won-two-thirds-of-nvidias-next-gen-high-bandwidth-memory-orders-industry-sources/12030483), [Tom's Hardware hybrid bonding](https://tomshardware.com/tech-industry/semiconductors/hybrid-bonding-roadmap-examined) (Apr 2026), Samsung Q3 call.
- Confidence: medium.
- Key: `tech_roadmap.hbm_trade_ratio` (see F1.8). Slow hybrid bonding plus 16-Hi deferral supports a modest ratio rise *only after* 2027. `constraints.hbm_backend`: MR-MUF and TC-NCF capacity is being chased successfully, which **SUPPORTS** the back-end being near-binding but not binding in 2026–27.

---

## 4. Supply side

**F4.1 – Wafer capacity by producer.**
- **SK hynix**: about **550k wpm DRAM in 2026 including ~200k at Wuxi**. M15X adds about 40k in 2H26, rising to about 80k in 2027 (another report says 70k). Yongin Fab 1 equipment install moved up to **Feb 2027**, adding about **360k wpm by 1H2030**. Yongin Y2 in 2H28. Target about **1M wpm by 2030–31**. Sources: [TrendForce/The Elec](https://www.trendforce.com/news/2026/06/05/news-sk%2Dhynix-reportedly-to-double-dram-capacity-to-1m-monthly-wafers-by-2030-speeds-yongin-expansion/), 2026-06-05; [Wccftech](https://wccftech.com/sk%2Dhynix-ceo-rings-alarm-bells-next-year-will-be-the-worst-year-in-the-industrys-history-from-the-supply-perspective/), 2026-07-21.
- **Samsung**: total DRAM about **650k wpm** (May 2026 report). P4 DRAM accelerated. **P5 Fab 1 begins July 2027.** P5 Fab 2 groundbreaking was pulled forward to July 2026. Combined P5 investment is about ₩120T, for **600k wpm of 300mm capacity at full operation in 2029** (the product split is not all DRAM). 2026 1c target about 200k wpm. Sources: [ninescrolls/Digitimes/Bloomberg](https://ninescrolls.com/news/samsung-pulls-forward-p5-fab-2-by-six-months-commits-82-7-billion-to-a-600-000/), 2026-05-13; [TrendForce](https://www.trendforce.com/news/2025/11/19/news-samsung-reportedly-plans-200k-1c-dram-wafersmonth-by-2026-about-one-third-of-its-total-output/).
- **Micron**: thin public data. ID1 output 2027–28; reported HBM wafer target about 100k/month by end-2026; NY is a $100bn multi-decade project. FY26 net capex $27.4bn. See the other session.
- **TrendForce**: 2026–27 bit growth comes mainly from node migration, with wafer starts up "only modestly" through process optimization, cleanroom acquisitions and reallocation (2026-09-07).
- Confidence: medium (press-reported plans, not guidance).
- Keys:
  - `supply_capacity.dram_wafer_capacity_kwspm.sk_hynix` = {2025: **595**, 2026: **620**, 2027: **670**, 2028: 720, 2030: **820**, 2032: 900}. **MIXED.** 2026 is roughly +30 kWSPM above the Elec figure (550 + 40 = ~590). 2030 is **~180 below** the stated 1M target, a big out-year gap if SK executes. Suggest 2026 ≈ 590–600, 2027 ≈ 650–670, 2028 ≈ 740, 2030 ≈ 900–950 (haircut on the 1M target).
  - `…samsung` = {2025: **720**, 2026: **780**, 2027: **840**, 2028: **900**, 2030: 1,000}. **MIXED.** The ~650k press figure is about 10% below the model's base. P5 Fab 1 from July 2027 and the full P5 in 2029 support the out-year 1,000. The near-term level may be overstated, and Samsung itself says 2027–28 bit adds are limited.
  - The model's base totals are calibrated to output (39–42 EB), so *levels* may be fine with density absorbing the difference. **Growth rates** are what matter: the 2027 industry wafer growth of ~+12% (SK hynix CEO) vs the model's +10% **SUPPORTS**.
  - **Bigger issue for the out-years:** the reported plans (SK 1M by 2030, Samsung P5 600k by 2029, Micron ID1/ID2/NY) are a *supply response* the July model treats as fixed. The 2029–2032 path probably needs to rise. See F4.2.

**F4.2 – Capex and WFE (the supply response is under way).**
- Samsung DS capex 2026 is KRW 76.8T (+62% YoY), with a "substantial" rise in 2027.
- SK hynix expects a significant 2027 capex increase.
- **Goldman: WFE $150bn (2026), $218bn (2027, +45%), $281bn (2028); DRAM WFE $48bn, then $72bn, then $97bn.** Needham: 2027 DRAM WFE about $84bn.
- ASML: memory **~46% of 3Q26 net system sales**; memory system sales **+~75% in 2026**; about 65 low-NA EUV shipped in 2026; 2027 low-NA nearly fully booked, with capacity +~30% (to about 85); evaluating a further +30% for 2028.
- Sources: [uanalyze/Goldman](https://uanalyze.com.tw/index.php/articles/6591753926), 2026-08-24; [Benzinga ASML Q3 transcript](https://www.benzinga.com/news/26/10/62356129), Oct 2026; [Morningstar](https://www.morningstar.com/stocks/asml-earnings-record-bookings-confirm-ai-upcycle-into-2027); [tradersunion](https://tradersunion.com/news/market-voices/show/2686002-asml-2027-euv-orders/).
- Confidence: medium.
- Keys:
  - `supply_capacity.dram_wafer_capacity_kwspm` 2029–2032 for all three. **CONTRADICTS (too low in the out-years).** DRAM WFE doubling from 2026 to 2028 is not compatible with the model's roughly +4–5%/yr capacity growth after 2028. This is the "no endogenous supply response" gap now showing up in announced plans.
  - `constraints.other_wfe.dram_supportable_kwspm`: **SUPPORTS** (slack).
  - `constraints.litho.euv_scanners_available_to_memory` = {2026: **58** (+13), 2027: **72** (+14), 2028: 88}. **CONTRADICTS (adds too low).** With memory at roughly 40–46% of ASML system sales, memory likely got **~25–30 new EUV tools in 2026** and **~30–38 in 2027**.

**F4.3 – Node ramps and EUV layers.**
- SK hynix 1c reaches about **35% of output by 1Q27** and becomes its main node. 1d development completes Dec 2026, with mass-production prep June 2027.
- Samsung 1d pilot is around end-2027 (reports conflict).
- EUV layers: **1b ≈ 4, 1c ≈ 5–6**.
- Sources: [TrendForce News](https://trendforce.com/news/2026/09/07/news-sk%2Dhynix-1c-dram-reportedly-to-overtake-1b-as-main-process-in-1q27-as-it-prepares-for-hbm4e), 2026-09-07; [Pause Hardware](https://pausehardware.com/sk%2Dhynix-1c-dram-2027/); [Wccftech](https://wccftech.com/sk%2Dhynix-reportedly-ramps-1c-dram-to-six-euv-layers/amp/).
- Confidence: medium.
- Keys:
  - `constraints.litho.euv_layers_per_dram_wafer` = {2026: **2**, 2027: **3**, 2028: 3.5}. **CONTRADICTS (too low)** for EUV-dependent wafers on 1b/1c, which run 4–6. Combined with F4.2 (more scanners), the two errors roughly offset, so C2 probably still does not bind in 2026–27. Both inputs should move together; suggest about 4 (2026), 5 (2027), 6 (2028). Re-check C2 in 2029+.
  - `tech_roadmap.dram_gb_per_wafer` (2026 2,260; 2027 2,385, about +5.5%/yr). **SUPPORTS**: migration-led bit growth plus a modest wafer add matches TrendForce's framing.

**F4.4 – 3D DRAM and 4F².** Samsung produced a **working 10a die using 4F² plus VCT** (March 2026). The schedule is development 2026, qualification 2027, **mass production 2028**, with 3D DRAM from 10d onward. Its CTO confirmed 4F² development in October without dates. SK hynix applies 4F²/VCT at 10b (later). Micron is reportedly skipping 4F² and moving to 3D stacking. CXMT's 4F² gives about 33% smaller cells, commercial after 2028. Sources: [TrendForce/The Elec](https://www.trendforce.com/news/2026/04/24/news-samsung-reportedly-produces-sub-10nm-10a-dram-working-die-using-4f-square-and-vct-targets-2028-production/), 2026-04-24; [Sammyfans](https://www.sammyfans.com/2026/10/22/samsung-sk%2Dhynix-micron-cxmt-4f2-dram-technology/amp/), 2026-10-22.
- Confidence: low-medium.
- Keys:
  - `tech_roadmap.three_d_dram.first_volume_year` = **2030**. **SUPPORTS for true 3D DRAM.**
  - 4F² is a separate, earlier density step (about 30% cell-area reduction, from 2028 at Samsung) that the model does not represent. The `dram_gb_per_wafer` path for 2028–2030 (+5%/yr) may be slightly low if Samsung's 10a ramps on schedule. Low confidence.

**F4.5 – CoWoS.**
- TSMC end-2026: **115–140k wpm**, or about **200k including OSATs** (ASE, Amkor; +50–60k).
- End-2027: about **170k** (KGI, Mar 2026). End-2028: about **260k** (doubling from about 130k at end-2026).
- The CoWoS supply-demand gap is narrowing from about 20% to about 10% by end-2026; TrendForce expects the 2.5D shortage to moderate in 2027.
- Sources: [TrendForce News](https://www.trendforce.com/news/2026/06/15/news-tsmc-cowos-supply-demand-gap-reportedly-seen-narrowing-from-20-to-10-by-end-2026-as-capacity-expands), 2026-06-15; [TrendForce News](https://www.trendforce.com/news/2026/09/14/news-tsmc-reportedly-targets-22-2nm-16-3nm-capacity-boost-by-mid-2027-cowos-to-double-by-2028/), 2026-09-14.
- Confidence: medium.
- Key: `constraints.advanced_packaging.cowos_wafers_kwpm` = {2026: **110**, 2027: **150**, 2028: **190**, 2029: 230}. **SUPPORTS for 2026–27** (TSMC-only, mid-year). **CONTRADICTS for 2028+**: about 225 (mid-2028) to 260 (end-2028) TSMC-only, more with OSATs. C6 is less likely to bind than the model implies; suggest 2028 ≈ 220–240 and 2029 ≈ 270.

---

## 5. Conventional demand

**F5.1 – Smartphones are collapsing (rationed outcome).**
- 3Q26: **255.3M units, −22.0% YoY** (IDC, the largest YoY decline on record). Counterpoint has about −20%.
- 2Q26: **277.5M, −6.7%** (IDC prelim, July).
- 2026 full year: IDC (Feb) **−12.9% to ~1.12bn**; Counterpoint **−13.9% to ~1.08bn**. Both are likely to be cut again after Q3. IDC's earlier 2027 view was +2%, with downside risk from inventory.
- TrendForce: average smartphone DRAM **8.5GB in 2026, +10% YoY** (the mix shifts away from low-RAM phones).
- Sub-$400 phones −22% in 2026 (Omdia). Samsung expects 2027 smartphone units to fall, mainly mid and entry tiers.
- Sources: [FoneArena/IDC](https://www.fonearena.com/blog/495163/global-smartphone-shipments-q3-2026-idc.html), Oct 2026; [databoks/IDC](https://databoks.katadata.co.id/en/technology-telecommunications/statistics/6a559e8630923/samsung-and-apple-lead-global-smartphone-shipments-in-the-second-quarter-of-2026), Jul 2026; [Telecoms.com/Counterpoint](https://www.telecoms.com/mobile-devices/smartphone-market-expected-to-be-a-bloodbath-this-year); [Mobile World Live/TrendForce](https://www.mobileworldlive.com/devices/smartphone-players-lower-specs-to-counter-costs/).
- Confidence: high (shipments); medium (forecasts).
- Keys:
  - `actuals.smartphone_units_millions_per_quarter[2026Q2]` = **288.0**. **CONTRADICTS.** The IDC prelim is 277.5; update.
  - New 2026Q3 actual: about **255**.
  - `demand_conventional.smartphone.units_millions` = {2026: **1,225**, 2027: 1,230}. Realized 2026 is about **1,050–1,100**. Per the README this is a *trend* demand series, so it should not be cut to rationed units.
  - **Flag for the modeller.** `actuals.yaml` says unit drivers are pinned to actuals through `actuals_end`. Extending actuals to 2026Q3 would inject a −22% rationed unit figure into the demand line, which conflicts with the "demand is unrationed" rule. Decide whether phone and PC units in the demand line stay on trend (recommended) or follow actuals.
  - `smartphone.dram_gb_per_unit` = {2026: **9.6**}. Realized is 8.5. **SUPPORTS** the gap interpretation: trend sits above realized.

**F5.2 – PCs.**
- 3Q26: IDC **62.7M (−20.1%)**; Gartner **55.4M (−22.4%)**; Omdia 58.1M (−21.2%); Counterpoint 57M (−21%).
- 2Q26: IDC **68.2M (−4.9%)** (Jul 11 prelim).
- 4Q26 forecasts: −24% (Omdia) to −27% (Counterpoint).
- **2027: −7%** (Omdia).
- IDC: 2026 PC ASP +18.3%; memory relief not before end-2027 or 2028.
- Client-SSD capacities are being cut in mainstream models.
- Sources: [TweakTown/IDC](https://www.tweaktown.com/news/114035/pc-shipments-fell-by-a-massive-20-year-over-year-last-quarter-and-yes-its-due-to-the-memory-crisis/index.html), 2026-10-08; [t2online/Gartner](https://t2online.in/tech/tech-news/global-pc-shipments-fall-22-4-per-cent-to-55-4-million-units-as-memory-costs-push-up-prices/2008589); [Digital Today](https://www.digitaltoday.co.kr/en/view/113170/q3-global-pc-shipments-plunge-more-than-20-percent-hit-by-ai-driven-memory-squeeze); [thetechoutlook/IDC Q2](https://www.thetechoutlook.com/tag/idc/), 2026-07-11.
- Confidence: high.
- Keys:
  - `actuals.pc_units_millions_per_quarter[2026Q2]` = **66.5**. IDC prelim is 68.2; **update**.
  - 2026Q3 is about 55–63 (tracker range).
  - `demand_conventional.pc.units_millions` = {2026: **262**, 2027: 265}. Realized 2026 is about **235–245**; 2027 is likely lower again. Same trend-vs-rationed caveat as F5.1. The 1H26 pull-forward IDC flagged has now reversed into a 2H26 hangover, which argues for a negative consumer `inventory_swing` in 2H26 and 2027.

**F5.3 – Servers: general-purpose demand is surging because of agentic AI.**
- TrendForce (4Q26 Server Market Report, 2026-11-02): **global server shipments up nearly 20% YoY in both 2026 and 2027**.
- **Server CPU shipments +31% in 2026, >+40% in 2027.** The CPU:GPU/ASIC ratio is moving **from 1:8 toward 1:2 or even 1:1** as agentic AI shifts workloads to CPU-side orchestration. Arm reaches about 30% of server CPUs by 2027.
- RDIMM bit supply grows only +15–20% in 2027, "failing to keep pace with server CPU shipment growth".
- Sources: [TrendForce report summary](https://www.trendforce.com/research/download/RP261102UN), 2026-11-02; [TrendForce via I-Connect007](https://iconnect007.com/article/152101/server-cpu-shipments-to-grow-over-40-in-2027-as-arm-gains-share/152098/pcb), 2026-10-22; [TrendForce PR](https://www.trendforce.com/presscenter/news/20260415-13013.html), 2026-04-15.
- Confidence: medium-high.
- Keys:
  - `demand_conventional.servers_traditional.units_millions` = {2026: **13.8** (+4.5%), 2027: **14.3** (+3.6%), 2028: 14.8}. **CONTRADICTS (too low).** A large new demand vector, CPU-heavy agentic-inference servers, is landing in the "traditional" bucket or in no bucket at all. Options:
    - (a) raise traditional server units to about +10–15%/yr for 2026–27; or
    - (b) add an "AI CPU / agentic server" segment to the inelastic core.
    - Either way, avoid double counting with `conventional_dram_gb_per_accelerator`.
  - `servers_traditional.dram_gb_per_unit` (2026: 1,190; 2027: 1,390). **SUPPORTS** as trend content, though realized RDIMM capacities were cut in 1H26.
  - `actuals.server_units_millions_per_quarter` (low confidence, derived). Consider re-basing.

**F5.4 – Graphics and consumer DRAM.** GDDR6 supply is shrinking and GDDR7 output limited; GDDR7 demand is driven mainly by AI chips. Some PC brands are reconsidering GDDR6 to cut BOM. Source: [TrendForce](https://www.trendforce.com/presscenter/news/20260930-13258.html), 2026-09-30.
- Confidence: medium.
- Key: `demand_conventional.graphics.dram_eb_per_year` (2026: 3.4; 2027: 3.9). **SUPPORTS.** Its note already says AI uses GDDR.

---

## 6. Other material items

**F6.1 – Export controls and tariffs.**
- Section 232 Phase 1 (effective 2026-01-15) is a 25% tariff on a narrow set of advanced AI chips with broad exemptions. **Memory is explicitly excluded.** USTR said in May that no immediate semiconductor tariffs were planned. I found **no memory tariff decision as of early November 2026**.
- CXMT remains **off the BIS Entity List** as of mid-2026, still subject to the Oct-2022 equipment rules. The Pentagon-list status is reported inconsistently.
- NVIDIA guides zero China DC compute revenue, and TrendForce says Chinese server shipments keep declining as domestic AI chips replace NVIDIA.
- Sources: [White & Case](https://www.whitecase.com/insight-alert/president-trump-orders-narrowly-targeted-25-section-232-tariff-certain-advanced), Jan 2026; [NTD/USTR](https://www.ntd.com/ustr-greer-says-no-immediate-semiconductor-tariffs-planned-emphasizes-sector-protection_1147706.html), 2026-05-23; [TrendForce bulletin](https://www.trendforce.com/research/download/RP260617EN), 2026-06-17; [TrendForce server report](https://www.trendforce.com/research/download/RP261102UN), 2026-11-02.
- Confidence: medium.
- Keys:
  - `china.policy_risk.export_control_tightening` = **0.0**. **SUPPORTS.**
  - `china.captive_share` = **1.0**. **SUPPORTS**: the China AI build is served domestically.
  - `china.domestic_dram_demand_eb_per_year`: Chinese domestic AI accelerators (Huawei Ascend with CXMT HBM) will grow it. No new number.

**F6.2 – KV cache, context-memory storage and HBF.**
- NVIDIA's BlueField-4 "Inference Context Memory Storage" platform creates a flash-based "G3.5" tier for KV cache at pod level. No per-GPU TB figure was found ([NVIDIA dev blog](https://developer.nvidia.com/blog/introducing-nvidia-bluefield-4-powered-inference-context-memory-storage-platform-for-the-next-frontier-of-ai/), Jan 2026).
- SanDisk and SK hynix published the first **HBF spec** (up to 512GB per package, 0.4–3.0 TB/s) on 2026-08-03; SanDisk taped out its first HBF die; **inference product samples in 2027** ([StorageReview](https://www.storagereview.com/news/sandisk%2Dtapes-out-its-first-hbf-memory-die-targets-2027-for-inference-product-samples), Aug 2026).
- Samsung says agentic AI drives demand for high-capacity TLC/QLC SSDs "through larger KV caches and dedicated cloud VMs for personal AI agents" (Q3 call).
- Confidence: medium.
- Keys:
  - `demand_ai.kv_cache.offload_to_nand_share` = {2025: 0.25, 2028: **0.45**, 2032: 0.60}. **SUPPORTS the direction.** HBF adds a NAND tier sitting *between* HBM and SSD from about 2028, which would raise the NAND offload share and possibly lower HBM content per unit. No numbers yet.
  - `nand_tb_per_accelerator` (see F1.12): **CONTRADICTS (too low).**

**F6.3 – CXL pooling.** No material new evidence of large-scale CXL pooling deployments since July. The industry trend is toward *more* host memory per AI server (SOCAMM, LPDDR), constrained by supply rather than pooled away.
- Confidence: low.
- Key: `demand_conventional.cxl_pooling_savings` (2027: 0.02, 2030: 0.065). **No change.**

---

## Ranked input changes for the November update

Ranked by how much each is likely to move the headline gap or fix a known mis-specification, weighted by
evidence quality.

1. **`demand_ai.hyperscaler_capex_usd_bn` and `avg_accelerator_asp_usd`: re-base together, and choose nominal or real explicitly.**
   - Nominal reality: about $850–960bn in 2026 and about $1.5tn in 2027, against the model's 620 and 850.
   - Much of the excess is memory and component price inflation: AI server units +36% vs capex +60% in 2027.
   - Either raise both capex and ASP to nominal (2027 capex ≈ $1.4–1.5tn, blended ASP ≈ $22–25k), or deflate to 2025 dollars and keep capex near its current values. Without this, the capex cross-check is meaningless.
   - Sources: F2.1, F2.2.
2. **`demand_ai.hbm_gb_per_accelerator` 2028–2032: flatten the slope.**
   - Rubin Ultra fell from 1TB to 192–384GB per package, and ASICs are evaluating 8-Hi.
   - Keep 2026 = 280 and 2027 ≈ 320–330. Bring 2028 to about 360–380 (from 410) and re-shape later years. Document that part of the cut is rationing, so trend content stays somewhat above shipped content.
   - Update the stale "Rubin Ultra ~1TB" notes in both files.
   - Sources: F3.2, F3.3.
3. **`demand_conventional.servers_traditional.units_millions` (or a new agentic-CPU segment): raise.**
   - TrendForce: servers about +20%/yr in 2026–27; server CPUs +31% and +40%; CPU:GPU ratio moving from 1:8 to 1:2.
   - Model: +4.5% and +3.6%.
   - This is the biggest *new* DRAM demand vector since July, and it belongs in the inelastic core.
   - Source: F5.3.
4. **NAND demand: `nand_tb_per_accelerator`, `servers_traditional.nand_tb_per_unit`, plus a new HDD→QLC substitution segment.**
   - Observed: a 2026 NAND deficit of 4–5%, eSSD bits >+80%, eSSD now more than half of NAND revenue.
   - The model shows NAND roughly balanced. Fix before trusting any NAND output.
   - Source: F1.12.
5. **`supply_capacity.dram_wafer_capacity_kwspm` out-years (2029–2032): raise to reflect the announced supply response.**
   - SK hynix targets 1M wpm by 2030 (model 820). Samsung P5 reaches 600k wpm of 300mm at full operation in 2029. DRAM WFE roughly doubles 2026–28.
   - Haircut the announcements, but the current ~+4–5%/yr out-year growth is too low. Near-term levels (Samsung 780 and SK 620 in 2026) look about 5–10% high versus press figures.
   - Sources: F4.1, F4.2.
6. **`tech_roadmap.hbm_wafer_share`: recheck the 2026 /0.844 conversion and set 2027 within 0.30–0.37.**
   - TrendForce: 22% in 2026, 30% in 2027, with an ambiguous denominator. Samsung: "nearly 30% of industry" in 2027.
   - Source: F1.7.
7. **`tech_roadmap.hbm_trade_ratio[2027]`: 3.05 → about 2.9, and flatten 2028+.**
   - TrendForce's own 2027 wafer and bit shares imply about 2.87.
   - Source: F1.8.
8. **`supply_capacity.nand_wafer_capacity_kwspm.ymtc`: raise.**
   - Already about 200k wpm, 13–14% of bits, Fab 3 coming. Suggest 2026 ≈ 200, 2028 ≈ 300, 2030 ≈ 400 (vs 155, 200, 240).
   - Captive, so global invariance holds, but NAND supply levels and the split move.
   - Source: F1.15.
9. **`demand_ai.conventional_dram_gb_per_accelerator`: raise 2026–27 trend content (175 and 200 → about 220–300).**
   - Vera host LPDDR is 380–750GB per GPU, and LPDDR covers only about 60% of NVIDIA's 2027 need. Reconcile with item 3 to avoid double counting.
   - Source: F3.4.
10. **`actuals.yaml` refresh.**
    - DRAM 2026Q2 revenue 152.3 → 154.73. PC 2026Q2 66.5 → 68.2. Smartphone 2026Q2 288 → 277.5.
    - Decide whether to extend `actuals_end` to 2026Q3 now (DRAM revenue est. $190–210bn, ASP +20–25%, bits +3–10%; PC about 55–63M; phones about 255M) or wait for TrendForce's early-December ranking. **Recommendation: wait.**
    - Resolve the policy question in F5.1: should rationed phone and PC units feed the demand line at all?
    - Sources: F1.1, F1.2, F5.1, F5.2.
11. **`demand_conventional.inventory_swing` 2027 (DRAM +1.0, NAND +20): cut toward zero or negative for the consumer channel.**
    - PC and phone OEMs are destocking 1H26 pull-forward; IDC flags a phone inventory build; CSP restocking offsets part of this.
    - Source: F1.5.
12. **`constraints.litho`: raise `euv_layers_per_dram_wafer` (to about 4/5/6 for 2026/27/28) and the `euv_scanners_available_to_memory` adds (about +25–30/yr) together.**
    - Each is about 2x off in opposite directions today. Re-test whether C2 binds after 2029.
    - Sources: F4.2, F4.3.
13. **`constraints.advanced_packaging.cowos_wafers_kwpm` 2028+: raise** (2028 ≈ 220–240, 2029 ≈ 270), and soften C6 for OSAT capacity.
    - Source: F4.5.
14. **`demand_ai.kv_cache.tokens_served_trillions`: correct the scale.**
    - Google alone was about 38,000T/yr in mid-2026, against a model value of 1,500 for 2026.
    - Also revisit `efficiency_deflator_annual` in light of the Jevons evidence (tokens 4–7x/yr while cost per token collapses).
    - Source: F2.7.
15. **China HBM: add a CXMT HBM term from 2027** (about 55k HBM wafer starts in 2027, about 100k in 2028, per SemiAnalysis; low confidence), and update the "CXMT makes no HBM" notes.
    - Source: F1.14.

**Values not to move** (evidence since July supports them):
- `datacenter.realisation_rate` (2026 0.62, 2027 0.52; Goldman 60% then 50%).
- `slip_quarters` = 3.
- `supply_capacity.dram_wafer_capacity_kwspm.cxmt` 2026–28.
- `constraints.hbm_backend` and `test` ceilings for 2026–27.
- `utilisation.dram` at 0.97.
- `china.captive_share` = 1.0.
- `three_d_dram.first_volume_year` = 2030 (4F² in 2028 is a separate, smaller density step).
