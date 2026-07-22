# Ground Truth Circularity Filter Report

53/150 question(s) dropped for sharing a 4+-word descriptive phrase with their own source chunk (proper nouns/dates exempted). 97 kept for evaluate.py (of which 0 could not be verified -- source chunk file missing -- and were kept rather than dropped unchecked).

**Scope reminder:** this catches verbatim phrase lifts only. Looser paraphrases of a citation's own title won't be caught here -- see this script's own module docstring.

## Dropped

- `accessnow-africa-2022-keepiton-shutdowns-chunk-0051` (flagged phrase: "during the august 2022")
  Q: Which East African country kept its commitment not to block internet access during the August 2022 general election, and how did that compare with Uganda’s approach?

- `cipesa-africa-2025-sifa-ai-chunk-0266` (flagged phrase: "ghana s 2022 national")
  Q: What priorities and governance measures do Ghana’s 2022 National AI Strategy and Senegal’s National AI Strategy (2023–2028) set out for ethical, rights-respecting AI?

- `accessnow-africa-2024-keepiton-shutdowns-chunk-0073` (flagged phrase: "launched ooni run v")
  Q: Which organization launched OONI Run v2 in 2024 to improve community-led censorship testing and faster response to network disruptions?

- `accessnow-africa-2024-keepiton-shutdowns-chunk-0029` (flagged phrase: "as high risk for")
  Q: Which countries were flagged as high-risk for election-related internet shutdowns in the 2024 #KeepItOn Election Watch campaign?

- `cipesa-africa-2025-sifa-ai-chunk-0133` (flagged phrase: "used by civil society")
  Q: What AI tools are being used by civil society in Tunisia to improve outreach and productivity?

- `accessnow-africa-2023-keepiton-shutdowns-chunk-0017` (flagged phrase: "the highest number of")
  Q: What was the highest number of internet shutdowns recorded in a single year since monitoring began in 2016?

- `cipesa-africa-2022-sifa-biometrics-chunk-0196` (flagged phrase: "independent data protection authorities")
  Q: Which countries named in the report lack independent data protection authorities to oversee biometric data collection and processing?

- `accessnow-africa-2022-keepiton-shutdowns-chunk-0061` (flagged phrase: "ethiopia s tigray region")
  Q: Since when has Ethiopia’s Tigray region been cut off from telecommunications services?

- `ooni-ke-2025-telegram-kcse-blocking-chunk-0052` (flagged phrase: "2024 kcse exam period")
  Q: What was the timing and scope of the Telegram service suspensions ordered in Kenya during the 2024 KCSE exam period?

- `ooni-tz-2024-lgbtiq-censorship-chunk-0046` (flagged phrase: "human rights websites in")
  Q: Which human rights websites in Tanzania were found to be blocked through TLS interference during the measured period?

- `ooni-ke-2025-telegram-kcse-blocking-chunk-0067` (flagged phrase: "during the 2024 kcse")
  Q: What did OONI data indicate about how Telegram Web was blocked on Jamil Telecommunications’ network during the 2024 KCSE exam period?

- `ooni-ug-2026-election-shutdown-and-blocking-chunk-0025` (flagged phrase: "internet access was restored")
  Q: Which social media platforms did OONI data indicate were blocked in Uganda after internet access was restored?

- `ooni-tz-2024-lgbtiq-censorship-chunk-0040` (flagged phrase: "access to the trevor")
  Q: What did OONI data suggest about access to The Trevor Project in Tanzania, and when did the blocking appear to begin?

- `ooni-ke-2025-telegram-kcse-blocking-chunk-0051` (flagged phrase: "mobile network operators to")
  Q: What action did Kenya’s Communications Authority order mobile network operators to take against Telegram during the 2024 KCSE exam period?

- `ooni-ug-2026-election-shutdown-and-blocking-chunk-0026` (flagged phrase: "access to instagram and")
  Q: What happened to access to Instagram and Twitter/X in Uganda after internet service was restored on January 18th?

- `ooni-tz-2024-lgbtiq-censorship-chunk-0027` (flagged phrase: "blocked in tanzania during")
  Q: Which LGBTIQ-related websites did OONI find to be blocked in Tanzania during the testing period?

- `ooni-tz-2024-lgbtiq-censorship-chunk-0021` (flagged phrase: "websites and social media")
  Q: What impact did the Tanzanian government’s crackdown on LGBTIQ-related websites and social media accounts have on online engagement by LGBTIQ people?

- `freedomhouse-ug-2022-fotn-chunk-0069` (flagged phrase: "for the release of")
  Q: Which social media campaigns did Ugandan activists use to press for the release of Kakwenza Rukirabashaija, Fred Lumbuye, and Stella Nyanzi?

- `cipesa-et-2025-sifa-ai-country-chunk-0088` (flagged phrase: "ai governance in ethiopia")
  Q: Who are the main actors shaping AI governance in Ethiopia, and which groups are left out of the consultation process?

- `ooni-ke-2025-telegram-kcse-blocking-chunk-0011` (flagged phrase: "over the past decade")
  Q: Which countries have been the focus of third-party research supported by OONI data over the past decade?

- `freedomhouse-ke-2024-fotn-chunk-0047` (flagged phrase: "and i am samuel")
  Q: What action did Kenya’s film board take against the movies Badhaai Do and I Am Samuel, and why did it say they were unsuitable for local viewers?

- `freedomhouse-ug-2022-fotn-chunk-0115` (flagged phrase: "the uganda government citizens")
  Q: What happened to the Uganda Government Citizens Interaction Centre’s Twitter account in March 2022, and what message did the hackers post after gaining access?

- `freedomhouse-rw-2022-fotn-chunk-0018` (flagged phrase: "the rwanda internet exchange")
  Q: Who manages the Rwanda Internet Exchange, and what concern do activists raise about the consolidation of telecommunications towers under IHS Towers?

- `cipesa-ug-2026-shutdown-economic-impact-chunk-0018` (flagged phrase: "during elections and other")
  Q: What actions does CIPESA recommend for businesses to better withstand internet disruptions during elections and other emergencies?

- `cipesa-ke-2025-sifa-ai-country-chunk-0044` (flagged phrase: "kenya s rapid adoption")
  Q: What risks does Kenya’s rapid adoption of AI pose for civic space and digital rights?

- `cipesa-et-2025-sifa-ai-country-chunk-0093` (flagged phrase: "supports democracy and protects")
  Q: What policy measures are recommended to make sure AI in Ethiopia supports democracy and protects civic space?

- `freedomhouse-et-2024-fotn-chunk-0128` (flagged phrase: "communications and related data")
  Q: Which Ethiopian legislation requires communications service providers to retain records of users’ communications and related data for at least one year and share them with the government on request?

- `freedomhouse-et-2023-fotn-chunk-0052` (flagged phrase: "ethiopia s media regulator")
  Q: What action did Ethiopia’s media regulator take against an association linked to the Ethiopian Orthodox Tewahedo Church after it broadcast a breaking news alert and shared a statement about tensions among bishops?

- `freedomhouse-ke-2022-fotn-chunk-0117` (flagged phrase: "during the covid 19")
  Q: What kind of online abuse did women in Kenyan politics face during the COVID-19 pandemic?

- `freedomhouse-et-2024-fotn-chunk-0108` (flagged phrase: "journalists from tigrai tv")
  Q: What happened to the journalists from Tigrai TV who were detained in Mekelle, and what was the outcome for the two who were still imprisoned at the end of 2023?

- `freedomhouse-et-2022-fotn-chunk-0035` (flagged phrase: "de facto authority over")
  Q: What changes were made to Ethiopia’s telecommunications regulator and the agency with de facto authority over the internet, and when did they occur?

- `freedomhouse-rw-2023-fotn-chunk-0029` (flagged phrase: "does the state block")
  Q: Does the state block or filter, or require service providers to block or filter, internet content, especially content protected by international human rights standards?

- `freedomhouse-et-2023-fotn-chunk-0029` (flagged phrase: "were involved in upgrading")
  Q: What foreign companies were involved in upgrading Ethiopia’s mobile networks and supplying SIM cards, and what concerns did their involvement raise about censorship and surveillance?

- `freedomhouse-ug-2024-fotn-chunk-0073` (flagged phrase: "the spread of misinformation")
  Q: Which government bodies were involved in efforts to curb the spread of misinformation during the pandemic and after the election protests?

- `freedomhouse-rw-2023-fotn-chunk-0056` (flagged phrase: "rwanda s supreme court")
  Q: What did Rwanda’s Supreme Court decide in 2019 about political cartoons and defamation of the president?

- `freedomhouse-ke-2025-fotn-chunk-0018` (flagged phrase: "that a major mobile")
  Q: What evidence is there that a major mobile operator gave security agencies access to customer call records and location data without judicial authorization?

- `freedomhouse-et-2023-fotn-chunk-0035` (flagged phrase: "be used for political")
  Q: What kinds of technology have Chinese authorities allegedly provided to the Ethiopian government that could be used for political repression?

- `freedomhouse-ug-2024-fotn-chunk-0050` (flagged phrase: "the social media blocks")
  Q: What was the outcome of the constitutional challenge to the social media blocks imposed during Uganda’s 2016 election period?

- `freedomhouse-ke-2024-fotn-chunk-0057` (flagged phrase: "for publishing hate speech")
  Q: What penalty can a media company in Kenya face for publishing hate speech, and how can that rule be used against online content?

- `freedomhouse-et-2022-fotn-chunk-0055` (flagged phrase: "supporters of the former")
  Q: What online manipulation tactics were used by supporters of the former Ethiopian government, and what rewards did they reportedly receive in return?

- `freedomhouse-ug-2023-fotn-chunk-0021` (flagged phrase: "during the january 2021")
  Q: Which online services were blocked in Uganda during the January 2021 elections, and what did the government do about internet access more broadly?

- `freedomhouse-rw-2025-fotn-chunk-0001` (flagged phrase: "for sim card registration")
  Q: What new rules did Rwanda introduce for SIM-card registration in August 2024?

- `freedomhouse-ug-2022-fotn-chunk-0006` (flagged phrase: "signed a deal with")
  Q: What did Alphabet do with Loon after Loon had signed a deal with the Ugandan government to bring 4G service to underserved areas?

- `cipesa-ke-2025-sifa-ai-country-chunk-0016` (flagged phrase: "s freedom on the")
  Q: What was Kenya’s Freedom on the Net 2024 score and overall internet freedom rating?

- `freedomhouse-ug-2022-fotn-chunk-0100` (flagged phrase: "the anti terrorism act")
  Q: What powers do Ugandan security officials have to access, intercept, and monitor private communications under the RIC Act and the Anti-Terrorism Act?

- `freedomhouse-ug-2022-fotn-chunk-0065` (flagged phrase: "major privately owned newspapers")
  Q: Which major privately owned newspapers in Uganda have online platforms that are only available in English?

- `freedomhouse-et-2023-fotn-chunk-0031` (flagged phrase: "under the telecom fraud")
  Q: What restrictions and licensing requirements do cybercafés in Ethiopia face under the Telecom Fraud Offences Proclamation of 2012?

- `freedomhouse-et-2022-fotn-chunk-0038` (flagged phrase: "12 th grade national")
  Q: Which social media platforms were restricted in Ethiopia after the 12th-grade national exam leak in November 2021?

- `freedomhouse-rw-2024-fotn-chunk-0022` (flagged phrase: "s mobile internet subscriptions")
  Q: What share of Rwanda’s mobile internet subscriptions did MTN Rwanda and Airtel Rwanda hold in September 2023?

- `freedomhouse-et-2023-fotn-chunk-0127` (flagged phrase: "civilians in amhara and")
  Q: What did the Ethiopian Human Rights Commission say about the ethnic attacks and retaliatory violence affecting civilians in Amhara and Oromia regions?

- `freedomhouse-et-2022-fotn-chunk-0041` (flagged phrase: "about the government s")
  Q: What legal or administrative steps have been used in Ethiopia to make online platforms take down content, and what happened to journalist Yayesew Shimelis after he posted about the government’s COVID-19 response?

- `freedomhouse-ke-2023-fotn-chunk-0088` (flagged phrase: "are there laws that")
  Q: Are there laws that impose criminal or civil penalties for online expression in Kenya?

- `cipesa-ug-2025-sifa-ai-country-chunk-0000` (flagged phrase: "digital democracy in uganda")
  Q: What is the title of the report on AI and digital democracy in Uganda, and when was it published?

