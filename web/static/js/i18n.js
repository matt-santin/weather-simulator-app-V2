/**
 * Every sentence the visitor reads, in one place.
 *
 * docs/application.md asks for this from the first line rather than later:
 * extracting the strings once the pages exist costs a sweep through every file,
 * and one always survives. There is one language today; the shape is what
 * matters.
 *
 * **The warning keys are named, and the naming is load-bearing.** CLAUDE.md
 * rule 1 forbids the vocabulary of forecasting on a future date, and a test
 * walks this object to enforce it — every string is checked, except the two
 * under `warning`, which exist precisely to deny the thing. Adding a third
 * exception means widening that list, which is the moment to notice.
 */

export const texts = {
  site: {
    skip: "Aller au formulaire",
    skipToDays: "Aller aux journées",

    // The link to the documentation page, on both pages that carry a search.
    //
    // **One key, and the whole phrase is the link.** The tempting shape was a
    // sentence with "ici" hung off the end, which costs twice: a link labelled
    // "ici" says nothing to anyone reading the links alone, and a sentence
    // split across two keys reorders wrongly the first time it is translated.
    // Set whole, it says where it goes and travels as one string.
    //
    // It sits under the warning on both pages, so it is worded as the answer to
    // the question that warning raises rather than as a menu entry.
    documentation: "Tout comprendre sur les données affichées",
  },

  // The banner asks before it explains. A site name at the top said what the
  // thing is called and nothing about what it is for; a question says both at
  // once, and the promise underneath settles it.
  //
  // The name is not lost — it stays in <title>, so in the tab and in a search
  // result, which is where a name is actually read.
  home: {
    // **Provisoire — à réécrire par le porteur du projet.** Un seul endroit.
    //
    // Deux contraintes. Une question porte un lieu et un horizon, sans quoi
    // elle n'évoque pas ce que le site sait faire. Et le vocabulaire de la
    // prévision reste proscrit : `present.test.js` parcourt ce tableau et
    // signalera la fautive sous `home.questions.<rang>`.
    //
    // Le test cherche la chaîne « il fera ». Il ne rattrapera donc pas « Quel
    // temps fera-t-il à Nice en 2050 ? », qui viole pourtant la règle 1 — ce
    // qu'aucune formulation ne doit faire, c'est promettre la journée.
    questions: [
      "Les étés seront-ils supportables dans 20 ans ?",
      "Comment seront les hivers dans les années 2040 ?",
      "Faut-il se marier en avril plutôt qu'en juin ?",
      "Faut-il passer ses vieux jours à Nice ou à Lille ?",
      "Cet été, vacances à Ajaccio ou à Berck-plage ?",
      "Investir dans un appartement sous les toits à Paris : bonne ou mauvaise idée ?",
      "Vélo ou rando cet hiver à la montagne ?",
      "Noël au balcon, Pâques avec glaçons ?",
      "Team canicule d’été ou inondation d’hiver ?"
    ],
    // The verb is what keeps this within rule 1: "simulez" is one of the three
    // terms it names as kept, and the sentence promises an exercise rather than
    // an outcome. It carries none of the forbidden words, and present.test.js
    // walks it like the rest.
    // The asterisk that qualifies this sentence is not in it: `home.js` cuts the
    // string before its full stop and puts the mark there, French typography
    // setting a footnote call ahead of the punctuation. The note it refers to is
    // `warning.note`, at the foot of the same page.
    //
    // **The line breaks are the string's own.** Where the promise breaks is
    // composition, not wrapping: a `max-width` narrow enough to force three
    // lines would break wherever the font happens to run out, and the font is
    // not a given — Georgia stands in until EB Garamond arrives over the
    // network, and sets the same sentence to a different length. So the breaks
    // are written here, next to the words they separate, and `home.js` sets one
    // line per "\n".
    //
    // Nothing is lost if that script never runs: HTML collapses a newline to a
    // space, so the `data-text` slot falls back to the whole promise on one
    // flowing line — which is the right thing to fall back to.
    promise:
      "Simulez la météo du futur.\n" +
      "Consultez celle du passé.\n" +
      "N'importe où. N'importe quand.",
  },

  form: {
    place: "Lieu",
    placeHint: "Une commune, une ville",
    from: "Du",
    to: "Au",
    submit: "Afficher la météo",
    searching: "Recherche du lieu…",
    candidates: (n) =>
      n === 1 ? "1 lieu trouvé, à choisir" : `${n} lieux trouvés, à choisir`,
    chosen: (label) => `Lieu : ${label}`,
    change: "changer",
    notFound: "Aucun lieu ne correspond à ce nom.",
    placeRequired: "Choisissez un lieu dans la liste.",

    // Two ways of asking for the same thing — a start and an end — so the
    // switch names the shape of the question, not what it will show. "Saison
    // entière" and not "Une saison" : the point is that none of it is missing.
    modeLabel: "Comment indiquer la période",
    modeDates: "Plage de dates",
    modeSeason: "Saison entière",
    season: "Saison",
    year: "Année",
    // The submit band is hidden until a panel is open, so this is only ever
    // reached by pressing Enter in the place field — which submits a form
    // whether or not it has a button on screen.
    periodRequired: "Choisissez une plage de dates ou une saison entière.",

    // Caught while the form is being filled in, so they are worded as
    // corrections rather than as refusals of a search that was really made.
    datesRequired: "Indiquez les deux dates.",
    rangeInverted: "La date de fin précède la date de début.",
    rangeOutsideCoverage: (first, last) => `Les dates vont de ${first} à ${last}.`,
    rangeTooLong: (max, asked) =>
      `${asked} jours demandés. Une recherche en porte ${max} au plus, soit une saison.`,
    rangeUnavailable: (periods) =>
      `Données indisponibles pour cette période. Dates disponibles : ${periods}.`,
    period: (from, to) => `${from} à ${to}`,
  },

  results: {
    range: (from, to) => `du ${from} au ${to}`,
    count: (n) => (n === 1 ? "1 journée" : `${n} journées`),
    loading: "Récupération des données…",
    back: "Nouvelle recherche",
    bandLabel: "Les journées, dans l'ordre. Défilement horizontal.",
    seam: "À partir d'ici, simulation",
  },

  // The chart says the same days as the strip, in the other reading. Its one
  // sentence points at the strip rather than repeating the numbers: every value
  // it draws is written out up there, which is what makes a drawing acceptable
  // to a reader who gets nothing from a drawing.
  chart: {
    // A function of one argument, and the argument is the label of the normals
    // or nothing. Two separate sentences would be the same sentence written twice,
    // to drift the day either is reworded.
    label: (normals) =>
      "Températures et précipitations de la période, jour par jour, " +
      "puis le cumul des précipitations dans un troisième panneau. " +
      "Les valeurs sont écrites dans la bande de journées ci-dessus." +
      (normals ? ` Les ${normals.toLowerCase()} y sont superposées en gris.` : ""),

    // What each panel plots, over it. The second says the same word as
    // `measure.precipitation` and is written twice on purpose: that one names a
    // number on a card, this one names a panel, and the day one of them is
    // reworded the other has no reason to follow.
    temperatures: "Températures",
    precipitation: "Précipitations",

    // The third panel, under the two above. It names the quantity in full
    // rather than saying "Cumul" alone: the word on its own would be read
    // against the panel it sits under, and there is more than one thing on this
    // drawing a total could be adding up.
    cumulative: "Cumul des précipitations",
  },

  // The seasonal normals of the temperatures.
  compare: {
    open: "Comparer aux normales de saison",
    reference: "Période de référence",
    loading: "Calcul des normales…",
    legend: (years) => `Normales ${years}`,
    method: (years, window) =>
      `Normales ${years} : pour chaque date, moyenne des 30 années sur ${window} jours ` +
      "centrés, au même lieu, d'après les réanalyses ERA5-Land et ERA5.",
  },

  // The climate diagram, under the chart. Its window is said with its source,
  // and a simulated one says so: rule 1 holds for twelve means as for a day.
  climate: {
    title: "Diagramme climatique",
    months: ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"],
    subtitle: (years, source, simulated) =>
      `Moyennes mensuelles ${years}, ${source}` +
      (simulated ? " : une simulation, pas une prévision." : "."),
    legendTemperature: (years) => `Température moyenne ${years}`,
    legendRain: (years) => `Précipitations ${years}`,
    legendReference: (years) => `${years}, en gris`,
    legendDry: "Mois sec",
    criterion:
      "Échelle de Bagnouls et Gaussen : 20 mm de pluie au niveau de 10 °C. " +
      "Un mois est sec quand ses précipitations (mm) sont au plus le double de sa " +
      "température moyenne (°C) : la barre reste sous la courbe.",
    summary: (years, temperature, rain, dry = []) =>
      `${years} : ${temperature} °C en moyenne annuelle, ${rain} mm par an, ` +
      (dry.length === 0
        ? "aucun mois sec."
        : `${dry.length === 1 ? "1 mois sec" : `${dry.length} mois secs`} (${dry.join(", ")}).`),
    monthNames: [
      "janvier", "février", "mars", "avril", "mai", "juin",
      "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ],
    label: (years, referenceYears) =>
      `Diagramme climatique du lieu : température moyenne et précipitations de chaque mois, ` +
      `${years}, et en gris ${referenceYears}. ` +
      "Les valeurs sont résumées sous le diagramme.",
    loading: "Calcul du diagramme climatique…",
  },

  // The matrix of years, under the climate diagram. The classes are the
  // server's (`/api/years`); their words are here.
  years: {
    title: (place) => `Toutes les années à ${place}`,
    intro: (from, to, reference, normal) =>
      `Du ${from} au ${to}, chaque année de 1970 à 2100. Couleur : écart de la température ` +
      `moyenne à celle de ${reference} (${normal} °C). Cliquez sur une année.`,
    legendCold: "Plus froid",
    legendNear: "Normale",
    legendWarm: "Plus chaud",
    legendSimulated: "Simulation (2027-2100)",
    legendNone: "Indisponible",
    temperature: {
      much_colder: "bien plus froid",
      colder: "plus froid",
      near: "proche de la normale",
      warmer: "plus chaud",
      much_warmer: "bien plus chaud",
    },
    rain: {
      much_drier: "bien plus sec",
      drier: "plus sec",
      near: "proche de la normale",
      wetter: "plus humide",
      much_wetter: "bien plus humide",
    },
    heading: (from, to) => `Du ${from} au ${to}`,
    simulated: "Simulation, pas une prévision.",
    temperatureLine: (mean, anomaly, reference, word) =>
      `Température moyenne ${mean} °C, ${anomaly} °C par rapport à ${reference} : ${word}.`,
    rainLine: (total, percent, word) =>
      `Précipitations ${total} mm, ${percent} % de la normale : ${word}.`,
    tileLabel: (year, mean, word) => `${year} : ${mean} °C, ${word}`,
    unavailable: (year) => `${year} : données indisponibles`,
    see: (year) => `Voir cette période en ${year}`,
    close: "Fermer",
    loading: "Calcul des années…",
    thresholds:
      "Température : proche de la normale à moins d'un demi-écart-type des années de " +
      "référence, bien plus chaud ou froid au-delà d'un écart-type et demi. Précipitations : " +
      "proche de la normale entre 80 et 120 %, bien plus sec sous 50 %, bien plus humide " +
      "au-dessus de 150 %.",
  },

  // The file the visitor takes away, and the words written in it.
  //
  // **`origin` is a column, so its three words are dictionary entries like any
  // other.** A file outlives the page it left: a temperature with no origin
  // beside it can be read years later as a measurement, which is the leak
  // CLAUDE.md rule 1 exists to close. The words are the site's own — a forecast
  // named a forecast, a projection named a simulation — which is why `forecast`
  // joins the sentences `present.test.js` exempts from the ban.
  //
  // **`columns` is a function, and that is what lets it borrow.** Two of its
  // headers are labels the page already declares: the unit, and « vent
  // maximal », which `docs/application.md` fixes as the label for a sustained
  // wind and forbids shortening to « vent ». Written out a second time here,
  // they would drift the day one of them is edited — and a header nobody rereads
  // is exactly where a drift survives. A literal cannot read the object it is
  // being declared in; a function called later can.
  //
  // The other headers are written out rather than borrowed: « Minimale » says
  // which of the two temperatures on a card that carries both, and says nothing
  // at all at the top of a column in a spreadsheet.
  export: {
    button: "Exporter mes données",
    columns: () => [
      "Date",
      "Origine",
      "Source",
      `Température minimale (${texts.units.celsius})`,
      `Température maximale (${texts.units.celsius})`,
      `${texts.measure.precipitation} (${texts.units.millimetres})`,
      "Nébulosité (%)",
      `Vent moyen (${texts.units.kilometresPerHour})`,
      `Température humide moyenne (${texts.units.celsius})`,
      "Chaleur humide",
      "Ciel",
    ],
    origin: {
      observed: "Réanalyse",
      simulated: "Simulation",
    },

    // **Le niveau part avec le nombre, et pour la raison qui fait partir
    // l'origine.** Un fichier survit à la page qu'il a quittée. « 31,2 » dans un
    // tableur, des années plus tard, se lit comme une douceur — c'est
    // exactement la fuite que la colonne d'origine existe pour fermer, et le
    // même remède la ferme : la qualification voyage sur la ligne, contre le
    // nombre qu'elle qualifie. Vide là où il n'y a rien à signaler, comme là
    // où il n'y a rien eu à mesurer.
    humidHeat: {
      0: "",
      1: "Chaleur humide",
      2: "Chaleur humide extrême",
    },
  },

  // Folded, but there. A corrected series read without knowing which model was
  // corrected, over which period, and when the table was built is a silent
  // source of error — docs/application.md says so, and this is the answer.
  provenance: {
    summary: "D'où viennent ces journées",
    model: "Modèle climatique",
    reference: "Correction calibrée sur",
    calibration: "Période de calibration",
    projection: "Période simulée",
    step: "Pas de la grille",
    generated: "Données préparées le",
    span: (from, to) => `${from} – ${to}`,
    degrees: (value) => `${value}°`,
    steps: (temperatures, rest) => `${temperatures} (températures), ${rest}`,
    observed:
      "Les journées passées viennent des réanalyses ERA5 et ERA5-Land (températures), " +
      "non d'un modèle climatique.",
    noGrid: "Aucune journée simulée : ces journées viennent des réanalyses ERA5 et ERA5-Land.",
  },

  // What a screen showing simulated days has to say, which is CLAUDE.md rule 1.
  //
  // **It was two lines and is one.** The second named the emissions scenario, a
  // statement `docs/science.md` requires of the interface — and gets, on the
  // documentation page, where there is room to add that the scenarios have not
  // parted by 2050 and that the single model weighs more than the trajectory.
  // Four words under a search rank the scenario without any of that, which
  // reads as more alarming than the measurement warrants.
  warning: {
    // The note the accueil's asterisk refers to, and it exists apart from the
    // compact line below for two reasons rather than one.
    //
    // **The results page cannot afford it.** That page is fitted to be seen
    // whole — measured at 893 px against a 960-pixel window — and this runs to
    // four or five lines where `notAForecast` runs to two, which pushes the
    // strip of days off the fold. The accueil has the room; the results page
    // has the strip.
    //
    // **And they are not the same statement.** `notAForecast` denies, which is
    // what rule 1 obliges on a screen already showing simulated days. This
    // explains, to a reader who has not run a search yet and is deciding
    // whether to.
    //
    // Two notes on the wording, both departures from what was drafted:
    //
    // "Au-delà des prochains jours" and not "Pour une date future". A date
    // inside the fortnight ahead *is* future and *is* a forecast — that is the
    // whole of the rule 1 amendment, and the earlier phrasing took it back. No
    // number here either, for the reason `provenance.forecast` gives: how far
    // the forecast reaches is a server constant.
    //
    // "du lieu et de la saison" and not "du lieu sélectionné". Nothing is
    // selected when this is read: it sits under the promise, above a form
    // nobody has filled in. And "saison" is the word rule 1 uses for what a
    // date actually situates.
    //
    // The period is the one number here, and it is served rather than written
    // — see `coverage` below. How far the forecast reaches still gets none, for
    // the reason `provenance.forecast` gives.
    //
    // "du climat futur", flatly, and not "du climat, actuel ou futur". The
    // hedge was wrong rather than cautious: the climate has no resting state,
    // so a day past the forecast falls under the climate of its own date and
    // never under today's. There is no branch to name.
    // The period covered, which opens the note because that is what the
    // asterisk qualifies — « N'importe quand* ».
    //
    // A function, because both ends are served. `/api/config` gives
    // `coverage_start` and `coverage_end`, and a 1950 written here would go on
    // saying 1950 the day the API said 1940: the copy rule 3 forbids, and the
    // reason `bounds.js` takes the same two dates from the same place. It is
    // also why this cannot be a `data-text` slot — `pages.test.js` refuses a
    // key that is not a sentence — so `home.js` fills it when the config lands.
    // Until then the slot is empty and the note still stands: the sentence
    // after it says where the forecast stops without needing the period.
    coverage: (periods) => `Dates disponibles : ${periods}.`,

    note: "Pour les dates futures, la météo affichée n'est pas une prévision, mais une simulation.",

    // The second line of the same note, and a line of its own rather than a
    // fourth sentence: the first says where the boundary falls, this says what
    // is on the far side of it. Two questions, two paragraphs.
    noteMeaning:
      "Cette météo simulée n'est pas le temps qu'il fera, mais le temps qu'il " +
      "pourrait faire, compte tenu du climat futur, du lieu et de la saison.",

    notAForecast:
      "Simulation, pas une prévision. La date situe la journée dans une saison, " +
      "elle n'engage rien sur ce jour-là.",
  },

  // The four names, in the order the form offers them, which is the order a
  // French year is recited in. The keys are the ones `season.js` writes and the
  // stylesheet paints — a test joins the three, because a season one of them
  // knows and another does not leaves the page with no ground and no word.
  season: {
    spring: "Printemps",
    summer: "Été",
    autumn: "Automne",
    winter: "Hiver",
  },

  sky: {
    clear: "Dégagé",
    cloudy: "Nuageux",
    overcast: "Couvert",
    rain: "Pluie",
    snow: "Neige",
    unknown: "Ciel indéterminé",
  },

  measure: {
    // Read aloud, not shown: the card carries "39 · 21", and warm against cool
    // is what says which is which — which is nothing at all to a screen reader,
    // or to anyone who does not separate the two colours. There is no
    // "Températures" label any more: the pair needs no word on screen.
    high: "Maximale",
    low: "Minimale",
    precipitation: "Précipitations",
    // The daily mean at 10 m, CORDEX serving no maximum: never "rafale".
    windMean: "Vent moyen",
    missing: "—",
    missingLabel: "donnée manquante",
  },

  // La chaleur humide, et le fait qu'on n'en écrive jamais le nombre.
  //
  // **Le mot porte le sens, le nombre non.** Une température humide n'a pas
  // d'échelle pour un lecteur : 31 °C est mortel et se lit comme une douceur, et
  // la carte porte déjà deux températures en gros. Les deux s'affichent depuis le
  // 7 septembre 2026, à la demande du porteur du projet, et c'est l'ordre qui
  // tient ce que l'arbitrage précédent visait : le mot arrive d'abord et nomme
  // ce qui suit, le nombre est composé comme une mesure et non comme un titre.
  //
  // **Deux niveaux, dits par le mot et par le poids.** Pas de second pictogramme
  // et surtout pas de tête de mort : une carte qui annonce une mort au 16 août
  // 2043 est l'assertion sur une date déterminée que la règle 1 proscrit, et
  // c'est aussi l'élément qui voyagerait le plus loin en copie d'écran, sans
  // l'avertissement qui l'entoure.
  //
  // **`note` décrit l'air et non le lecteur**, ce qui est ce qui la met hors
  // d'atteinte de la règle 1 sur une journée simulée. Elle n'énonce aucun seuil
  // de survie : ce serait une affirmation médicale sur une date.
  humidHeat: {
    mark: "⚠️",
    level: {
      1: "Chaleur humide",
      2: "Chaleur humide extrême",
    },
    // Read aloud in front of the figure, and never shown: the word above it on
    // the card already says which quantity this is, and writing the full name
    // twice would leave no room for anything else on a hundred-pixel card. Same
    // division as `measure.windMax`, which labels a number the card prints bare.
    valueLabel: "Température humide moyenne",
    reading: (value) => `Température humide moyenne : ${value} ${texts.units.celsius}`,
    note: {
      1:
        "Chaleur humide : l'air est assez chargé en vapeur d'eau pour que la " +
        "transpiration ne suffise plus à refroidir le corps.",
      2:
        "Chaleur humide : l'air est assez chargé en vapeur d'eau pour que la " +
        "transpiration ne suffise plus à refroidir le corps. Au niveau extrême, " +
        "elle n'y suffit plus même au repos, et la nuit n'apporte pas de répit.",
    },
    noteLink: "Comment cette valeur est calculée",
  },

  units: {
    celsius: "°C",
    millimetres: "mm",
    kilometresPerHour: "km/h",
  },

  // Handed to fetch.js, which transports and does not write. Separate sentences
  // because the failures are not the visitor's to confuse: Open-Meteo answering
  // badly is the common one, and its rate limit counts against their own
  // address, so waiting is something they can actually do.
  //
  // `tookTooLong` is the fourth, and it exists because the advice differs. A
  // stalled request is not a refused one: nothing was answered, nothing counted
  // against anybody, and there is no reason to wait — the thing to do is ask
  // again. Folded into `upstreamFailed` it would have told a visitor to sit out
  // a rate limit they never hit.
  transport: {
    upstreamFailed:
      "La recherche de lieux n'a pas abouti. " +
      "Le service Open-Meteo limite le nombre de recherches ; réessayez dans un moment.",
    tookTooLong: "Le service met trop longtemps à répondre. Relancez la recherche.",
    serviceFailed: "L'application est momentanément indisponible.",
    searchFailed: "La recherche n'a pas abouti.",
  },
};
