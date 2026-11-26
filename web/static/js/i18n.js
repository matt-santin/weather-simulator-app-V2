/**
 * Every sentence the visitor reads, in one place.
 *
 * docs/application.md asks for this from the first line rather than later:
 * extracting the strings once the pages exist costs a sweep through every file,
 * and one always survives. There is one language today; the shape is what
 * matters.
 *
 * **The warning keys are named, and the naming is load-bearing.** Rule 1 of the
 * V1 CLAUDE.md forbids the vocabulary of forecasting on a future date, and a test
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
    // The legal notice (LCEN), under the documentation link of the home page.
    legal: "Mentions légales",
  },

  // The bar of the results and the map (nav.js).
  nav: {
    label: "Navigation entre le lieu et la carte",
    home: "Météo 2100",
    map: "Carte",
    placeTitle: (place) => `La saison à ${place}, jour par jour`,
    mapTitle: "La même saison sur la carte d'Europe",
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
    // The name of the asterisk of the promise, read aloud: it opens the note.
    noteHint: "Dates disponibles et simulation",
    example: "Visualisez l'été 2075 à Paris",
    promise:
      "Simulez la météo du futur.\n" +
      "Consultez celle du passé.\n" +
      "Partout en Europe. N'importe quand.",
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
    outside: "Ce lieu est hors de la zone couverte (Europe).",
    placeRequired: "Choisissez un lieu dans la liste.",

    // Two ways of asking for a season: by its year, or by its kind in an
    // epoch, the year then drawn at random (kinds.js). Both give a whole
    // season; the names say what the visitor picks: a year, or a kind.
    periodLabel: "Période",
    modeSeason: "Choisir une année",
    modeKind: "Choisir un type de saison",
    season: "Saison",
    year: "Année",
    epoch: "Époque",
    // The label of the kind list follows the season: "Un été plutôt…". The
    // seasons are all masculine, so the adjectives below agree with each.
    kindPrompt: (season) => `Un ${season} plutôt…`,
    // In the list, the drawn kinds only: they read on from the label (un été
    // plutôt chaud).
    kindChoices: { cool: "frais", normal: "normal", warm: "chaud" },
    kindChoicesWinter: { cool: "froid", normal: "normal", warm: "doux" },
    // Under the list, boxes for the records and the extreme day, on the side
    // of the kind chosen (kinds.js, extrasOf).
    kindExtras: {
      coldRecord: "Voir le record de fraîcheur",
      record: "Voir le record de chaleur",
      hottestDay: "Voir le jour le plus chaud",
      coldestDay: "Voir le jour le plus froid",
    },
    kindExtrasWinter: {
      coldRecord: "Voir le record de froid",
      record: "Voir le record de douceur",
      coldestDay: "Voir le jour le plus froid",
    },
    epochs: {
      old: "Ancien climat",
      new: "Nouveau climat",
      future: "Climat futur",
    },
    epochOption: (label, first, last) => `${label} (${first}-${last})`,
    // Seasons are masculine in French: un été frais, un hiver doux.
    kinds: {
      coldRecord: "Record de fraîcheur",
      cool: "Frais",
      normal: "Normal",
      warm: "Chaud",
      record: "Record de chaleur",
      hottestDay: "Jour le plus chaud",
      coldestDay: "Jour le plus froid",
    },
    kindsWinter: {
      coldRecord: "Record de froid",
      cool: "Froid",
      normal: "Normal",
      warm: "Doux",
      record: "Record de douceur",
      coldestDay: "Jour le plus froid",
    },
    kindHint: "Comment le type est choisi",
    kindNote:
      "Une saison tirée au hasard parmi celles de l'époque, classées par la moyenne " +
      "des températures maximales au lieu choisi : les 20\u00a0% les plus fraîches, les " +
      "60\u00a0% du milieu ou les 20\u00a0% les plus chaudes. Les records sont la saison " +
      "la plus chaude et la plus fraîche de l'époque (la plus douce et la plus froide en " +
      "hiver), toujours les mêmes. Le jour le plus chaud ouvre la saison de la journée " +
      "à la température maximale la plus haute de l'époque, le jour le plus froid celle " +
      "de la nuit à la température minimale la plus basse.",
    drawing: "Tirage d'une année…",
    noYear: "Aucune année de ce type pour cette époque.",
    // The submit band is hidden until a panel is open, so this is only ever
    // reached by pressing Enter in the place field, which submits a form
    // whether or not it has a button on screen.
    periodRequired: "Choisissez une année ou un type de saison.",

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
    // Under the dates, when the temperatures were brought to the altitude of the place.
    altitude: (metres) => `Températures à l'altitude du lieu : ${metres}\u00a0m`,
    altitudeHint: "D'où vient cette altitude",
    altitudeMethod: (place, cell) =>
      `Les températures sont connues par mailles d'environ 8 km de côté. Celle de ce lieu est à ` +
      `${cell}\u00a0m d'altitude moyenne : ses températures sont ramenées à ${place}\u00a0m, altitude du lieu, ` +
      "par un gradient propre à chaque mois. Les précipitations ne sont pas corrigées.",
    count: (n) => (n === 1 ? "1 journée" : `${n} journées`),
    // The last line of an enlarged day: a click on it opens the map of that day.
    dayOnMap: "Voir ce jour sur la carte d'Europe ›",
    loading: "Récupération des données…",
    back: "Nouvelle recherche",
    seasonSwitch: "Changer de saison",
    seasonUnavailable: "données indisponibles",
    daysMore: (n) => `Afficher les ${n} journées`,
    daysLess: "Replier les journées",
    bandLabel: "Les journées, semaine par semaine, du lundi au dimanche. Flèches pour passer d'un jour à l'autre.",
    seam: "À partir d'ici, simulation",
    // On the first simulated card of the calendar, beside the month name.
    seamCard: "simulation",
    weekdays: ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."],
    // The legend under the calendar: its title, and the bounds of each band.
    legendTitle: "Température maximale (°C)",
    legendBelow: (edge) => `< ${edge}`,
    legendBetween: (low, high) => `${low}-${high}`,
    legendAbove: (edge) => `≥ ${edge}`,
  },

  // The chart says the same days as the strip, in the other reading. Its one
  // sentence points at the strip rather than repeating the numbers: every value
  // it draws is written out up there, which is what makes a drawing acceptable
  // to a reader who gets nothing from a drawing.
  chart: {
    // A function of one argument, and the argument is the label of the normals
    // or nothing. Two separate sentences would be the same sentence written twice,
    // to drift the day either is reworded.
    label: (normals, snow = false, soil = false) =>
      "Températures et précipitations de la période, jour par jour, " +
      "puis le cumul des précipitations dans un troisième panneau. " +
      "Les valeurs sont écrites dans la bande de journées ci-dessus." +
      (normals ? ` Les ${normals.toLowerCase()} y sont superposées en gris.` : "") +
      (snow ? " Les jours de neige au sol sont sur fond bleuté dans le panneau des précipitations." : "") +
      (soil ? " Un quatrième panneau montre l'eau restant dans le sol, de 0 à 100 % de sa réserve utile." : ""),

    // The ground under the bars of the rain panel, named on its title line.
    snow: "Neige au sol",

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

    // The fourth panel, when the server serves it: what is left of the water
    // the soil holds for the plants (src.app.domain.soil).
    soil: "Eau du sol (part de la réserve utile)",
    // The legend of the soil panel when the normals carry their extremes.
    soilRange: (label) => `${label}, plus sec et plus humide`,
  },

  // The seasonal normals of the temperatures.
  // The summary card at the top of the results page (summary.js).
  summary: {
    heading: (season, years, place) => `${season} ${years}${place ? ` à ${place}` : ""}`,
    hint: "Comment ces chiffres sont calculés",
    method: (reference) =>
      `Chaque chiffre est comparé à sa normale : sa moyenne sur les mêmes dates des années ` +
      `${reference}, au même lieu. ` +
      "Seuils de DRIAS (Météo-France) : 35\u00a0°C pour les jours de très forte chaleur, " +
      "20\u00a0°C pour les nuits tropicales, 25\u00a0°C pour les journées estivales, 0\u00a0°C pour le " +
      "gel. Le seuil de 40\u00a0°C est propre au site.",
    normal: (reference, value) => `normale ${reference} : ${value}`,
    tasmax_mean: (value) => `température maximale moyenne : ${value}\u00a0°C`,
    tas_mean: (value) => `température moyenne : ${value}\u00a0°C`,
    hot_35: (n, forty) =>
      `${n < 2 ? "jour" : "jours"} à 35\u00a0°C ou plus` +
      (forty ? `, dont ${forty} à 40\u00a0°C ou plus` : ""),
    tropical_nights: (n) =>
      `${n < 2 ? "nuit tropicale" : "nuits tropicales"} (minimale au-dessus de 20\u00a0°C)`,
    summer_days: (n) => `${n < 2 ? "journée" : "journées"} au-dessus de 25\u00a0°C`,
    frost_days: (n) => `${n < 2 ? "jour" : "jours"} de gel (minimale sous 0\u00a0°C)`,
    precipitation: (total) => `de pluie par rapport à la normale (${total}\u00a0mm)`,
    // A mean of the winters around the one shown, and said so: no winter has its own count.
    snow: (n, years) =>
      `${n < 2 ? "jour" : "jours"} de neige au sol par hiver, en moyenne sur ${years}`,
    snowMethod:
      " La neige au sol est une moyenne sur les 15 années autour de l'hiver affiché, pas le compte " +
      "de cet hiver : voir le climat du lieu, plus bas.",
    // Where the season stands among the observed ones (summary.js, `standing`).
    // Every season name is masculine; "printemps" does not change in the plural.
    seasons: { summer: ["été", "étés"], winter: ["hiver", "hivers"], spring: ["printemps", "printemps"], autumn: ["automne", "automnes"] },
    // The words of the kinds of the form: chaud and frais, doux and froid in winter.
    warm: { summer: "chaud", winter: "doux", spring: "chaud", autumn: "chaud" },
    cool: { summer: "frais", winter: "froid", spring: "frais", autumn: "frais" },
    warmPlural: { summer: "chauds", winter: "doux", spring: "chauds", autumn: "chauds" },
    rankAll: (side, total, plural, span, other) =>
      `Plus ${side} que les ${total} ${other ? "autres " : ""}${plural} observés ${span}.`,
    rankFew: (n, singular, plural, side, sides, span, years) =>
      n === 1
        ? `Un seul ${singular} observé ${span} a été plus ${side} : ${years}.`
        : `Seuls ${n} ${plural} observés ${span} ont été plus ${sides} : ${years}.`,
    rankMost: (side, n, total, plural, span, other) =>
      `Plus ${side} que ${n} des ${total} ${other ? "autres " : ""}${plural} observés ${span}.`,
    rankSpan: (first, last) => `de ${first} à ${last}`,
    rankMethod:
      " Le classement compare la moyenne des températures maximales à celle des mêmes dates " +
      "de chaque année observée.",
    // The kind the season was drawn from on the home form (results.js, `showKind`).
    epochOf: { old: "de l'ancien climat", new: "du nouveau climat", future: "du climat futur" },
    drawn: (singular, kind, epoch, first, last) =>
      `Un ${singular} ${kind.toLowerCase()} ${epoch} (${first}-${last}), tiré au hasard.`,
    fixed: (kind, epoch, first, last) => `${kind} ${epoch} (${first}-${last}).`,
    redraw: "Tirer une autre année",
    redrawing: "Tirage…",
    loading: "Calcul de la synthèse…",
    more: "Voir cette saison parmi toutes les années",
    mapLink: "Voir cette saison sur la carte d'Europe",
    ways: "Aller plus loin",
  },

  // "À voir aussi", at the foot of the results page (suggest.js, results.js).
  suggest: {
    title: "À voir aussi",
    next: "Saison suivante",
    previous: "Saison précédente",
    // "Un été moyen de 1991-2020"; every season name is masculine.
    typical: (singular, first, last) => `Un ${singular} moyen de ${first}-${last}`,
    elsewhere: "Mêmes dates, ailleurs",
    meanMaximum: (value) => `Maximales : ${value} en moyenne`,
    against: (value) => `, contre ${value}`,
    againstPlace: (value, place) => `, contre ${value} à ${place}`,
    maximum: (value) => `Maximale : ${value}`,
    minimum: (value) => `Minimale : ${value}`,
    dayTitle: (date, place) => `${date} à ${place}`,
  },

  // The "Partager" pill and its window (sharing.js), the foot of the picture
  // (sharecard.js).
  share: {
    open: "Partager cette saison",
    title: "Partager cette saison",
    close: "Fermer",
    formats: "Format de l'image",
    square: "Carré",
    story: "Story",
    native: "Partager…",
    copy: "Copier le lien",
    download: "Télécharger l'image",
    copied: "Lien copié.",
    copyFailed: (url) => `Copie impossible : ${url}`,
    downloaded: "Image téléchargée.",
    failed: "Partage impossible.",
  },

  compare: {
    open: "Comparer aux normales de saison",
    hint: "Comment les normales sont calculées",
    loading: "Calcul des normales…",
    legend: (years) => `Normales ${years}`,
    method: (years, window) =>
      `Normales ${years} : pour chaque date, moyenne des 30 années sur ${window} jours ` +
      "centrés, au même lieu, d'après E-OBS (températures) et la réanalyse ERA5. " +
      "Pour l'eau du sol, même moyenne du bilan hydrique de ces 30 années.",
  },

  // The climate diagram, under the chart. Its window is said with its source,
  // and a simulated one says so: rule 1 holds for twelve means as for a day.
  climate: {
    title: "Le climat du lieu, mois par mois",
    hint: "Comment lire le diagramme",
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
    // Snow on the ground, under the two lines of the summary. A simulated
    // figure is scaled from the observed one (`baseline`), and says so.
    snowHint: "Comment la neige au sol est comptée",
    snowDays: (days) => {
      if (days === 0) return "aucun jour";
      const whole = Math.round(days);
      if (whole === 0) return "moins d'un jour";
      return whole === 1 ? "1 jour" : `${whole} jours`;
    },
    snow: (own, years, reference, referenceYears) =>
      `Neige au sol : ${own} par hiver en ${years} ; ${reference} par hiver en ${referenceYears}.`,
    snowRare: (years, reference, referenceYears) =>
      `Neige au sol : trop rare pour être chiffrée en ${years} ; ` +
      `${reference} par hiver en ${referenceYears}.`,
    snowMethod: (baseline) =>
      "Jours avec de la neige au sol, de novembre à avril, en moyenne par hiver. Ils sont calculés à " +
      "partir des températures et des précipitations du lieu : la neige s'accumule les jours froids et " +
      "fond dès qu'il dégèle. Écart habituel aux observations : environ une semaine par hiver. " +
      "Non calculé au-dessus de 800 m." +
      (baseline
        ? ` Pour une période simulée, le nombre observé en ${baseline} est multiplié par l'évolution ` +
          "que le modèle donne depuis ces années. Le modèle se réchauffe en retard sur les observations : " +
          "le recul de la neige est plutôt sous-estimé, et le nombre peut remonter entre les dernières " +
          "années observées et les premières années simulées."
        : ""),
  },

  // The matrix of years, under the climate diagram. The classes are the
  // server's (`/api/years`); their words are here.
  years: {
    title: (place) => `Toutes les années à ${place}`,
    intro: (from, to, reference, normal) =>
      `Du ${from} au ${to}, chaque année de 1970 à 2100. Couleur : écart de la température ` +
      `moyenne à celle de ${reference} (${normal} °C). Cliquez sur une année.`,
    hint: "Seuils des commentaires",
    legendCold: "+ froid",
    legendNear: "Normale",
    legendWarm: "+ chaud",
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
    // After the verdict and an icon: "Bien plus chaud [thermometer] 23,3 °C, +4,0 °C".
    temperatureFigures: (mean, anomaly) => `${mean}\u00a0°C, ${anomaly}\u00a0°C`,
    // No break inside "111 % de la normale": the line wraps after the comma or not at all.
    rainFigures: (total, percent) => `${total}\u00a0mm, ${percent}\u00a0%\u00a0de\u00a0la\u00a0normale`,
    // The names of the icons, read aloud in their place.
    iconTemperature: "Température moyenne",
    iconRain: "Précipitations",
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

  // The map page. Every sentence it shows, as on every other page.
  maps: {
    pageTitle: "Cartes météo",
    homeLink: "Cartes météos",
    back: "Météo 2100",
    title: (variable, season, year) => `${variable}, ${season.toLowerCase()} ${year}`,
    variable: "Grandeur",
    isobars: "Isobares",
    cities: "Villes",
    variables: {
      tasmax: "Températures maximales",
      tasmin: "Températures minimales",
      pr: "Précipitations",
      clt: "Nébulosité",
      soil: "Eau du sol",
      soil_anomaly: "Anomalie d'humidité du sol",
    },
    eyebrow: "Cartographie, Europe",
    sourceTitle: "Sources et méthode",
    season: "Saison",
    year: "Année",
    // The simulation is the one /api/config names (the store's), never written here.
    simulated: (simulation) =>
      "Les journées après 2026 viennent d'une simulation climatique, sous le scénario " +
      `${simulation.scenario} : une météo plausible pour la saison et le climat de son ` +
      "époque, pas le temps qu'il fera ce jour-là.",
    play: "Lecture",
    pause: "Pause",
    previous: "Jour précédent",
    next: "Jour suivant",
    speed: "Vitesse",
    speeds: { 1: "1 jour/s", 3: "3 jours/s", 8: "8 jours/s" },
    timeline: "Choisir la journée",
    zoomIn: "Zoomer",
    zoomOut: "Dézoomer",
    zoomWhole: "Voir toute l'Europe",
    dayOf: (index, total) => `Jour ${index} sur ${total}`,
    distribution: "Répartition des mailles",
    loading: "Chargement de la carte…",
    mapLabel: "Carte d'Europe de la grandeur choisie, pour la journée affichée",
    source: (simulation, isobars) =>
      "Valeurs journalières sur les mailles terrestres de 0,25° (environ 28 km) : " +
      "températures maximale et minimale, cumul de précipitations, nébulosité moyenne. " +
      "1970-2025 : réanalyse ERA5, températures E-OBS (ERA5 là où il manque). " +
      `2027-2100 : CORDEX ${simulation.domain} ` +
      `(${simulation.driving} / ${simulation.regional}) corrigé ` +
      "contre ces mêmes données. Un jour de pluie compte au moins 1 mm (DRIAS, Météo-France). " +
      (isobars
        ? "Isobares : pression au niveau de la mer, une ligne tous les 5 hPa, sur une " +
          "grille de 0,5°, lissée. "
        : "") +
      "Eau du sol : part de la réserve utile du sol encore disponible en fin de journée, " +
      "100 % à la capacité au champ, 0 % au point de flétrissement ; bilan hydrique " +
      "journalier d'une prairie de référence (FAO-56), réserve utile du sol d'ESDAC (Hiederer 2013), " +
      "100 mm là où elle manque. " +
      "Anomalie d'humidité du sol : la même eau comparée à sa normale, moyenne ERA5 1991-2020 " +
      "du même jour de l'année (lissée sur 31 jours), en points de réserve utile ; négative, " +
      "le sol est plus sec que d'habitude. La même normale sert au passé et à la simulation. " +
      "Contours : Natural Earth. Noms des lieux : GeoNames (CC BY 4.0).",
    north: "N",
    south: "S",
    east: "E",
    west: "O",
    // The place the visitor came from (the results page), marked on the map.
    here: (place) => `À ${place}`,
    hereLink: (place) => `Voir la saison à ${place}`,
    // A cell clicked: its value, the town it is near, the way to its results.
    pick: {
      searching: "Recherche du lieu…",
      near: (name, country) => `Près de ${name}${country ? ` (${country})` : ""}`,
      at: (name, country) => `${name}${country ? ` (${country})` : ""}`,
      link: "Voir cette saison ici",
      close: "Fermer",
      hint: "Cliquez sur une maille pour voir sa saison en détail.",
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
      "Les journées passées viennent d'observations (E-OBS, températures) et de la " +
      "réanalyse ERA5, non d'un modèle climatique.",
    noGrid: "Aucune journée simulée : ces journées viennent d'E-OBS (températures) et de la réanalyse ERA5.",
    altitude: (place, cell) =>
      `Températures ramenées de l'altitude moyenne de la maille (${cell} m) à celle du lieu (${place} m), ` +
      "par un gradient propre à chaque mois.",
  },

  // What a screen showing simulated days has to say, which is the V1 CLAUDE.md rule 1.
  //
  // **It was two lines and is one.** The second named the emissions scenario, a
  // statement the V1's `docs/science.md` requires of the interface — and gets, on the
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
      "La météo dans le futur est simulée et n'est pas le temps qu'il fera, mais le " +
      "temps qu'il pourrait faire, compte tenu du climat futur, du lieu et de la saison.",

    hint: "Ce que cela veut dire",
    detail:
      "La date situe chaque journée dans une saison et dans le climat de son " +
      "époque ; elle n'engage rien sur ce jour-là.",
    notAForecast: "Simulation : une météo plausible, pas une prévision.",
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
    humidity: "Humidité relative",
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
    percent: "%",
  },

  // The table of the enlarged card: every reading, one line each, the word
  // shown this time since the card has the room.
  detail: {
    // The box beside the maximum of the enlarged tile: its gap to the normal.
    gap: (value) => `${value}\u00a0°C`,
    gapTitle: "Écart à la normale de saison (5 °C ou plus : jour anormalement chaud ou froid, DRIAS)",
    high: "Température max.",
    low: "Température min.",
    precipitation: "Précipitations",
    humidity: "Humidité",
    wind: "Vent moyen",
    snow: "Neige au sol",
    soil: "Eau du sol",
    yes: "oui",
  },

  // Snow on the ground, day by day: the mark of a card, the line under the
  // calendar and its "?".
  // The water left in the soil (src.app.domain.soil): the line under the chart
  // and its "?".
  soil: {
    hint: "Comment l'eau du sol est calculée",
    lowest: (value, day) => `Eau du sol au plus bas : ${value} % de la réserve utile, le ${day}.`,
    method: (simulated) =>
      "L'eau du sol n'est pas mesurée : elle est calculée jour après jour pour une prairie de " +
      "référence (méthode FAO-56). La pluie et la fonte de la neige remplissent le sol ; " +
      "l'évaporation et la transpiration de l'herbe le vident, d'autant plus lentement qu'il est sec. " +
      "100 % : le sol tient toute l'eau qu'il peut garder pour les plantes (sa réserve utile, sur un " +
      "mètre au plus) ; 0 % : les racines n'en tirent plus rien. Sous 50 %, l'herbe commence à manquer " +
      "d'eau. Une forêt ou une culture réelle se comporterait autrement. Réserve utile : European Soil " +
      "Data Centre (ESDAC, Hiederer 2013), 100 mm là où elle manque." +
      (simulated ? " Pour une année simulée, c'est le sol d'une année possible du modèle." : ""),
  },

  snow: {
    onGround: "Neige au sol",
    legend: "neige au sol",
    hint: "Comment la neige au sol est estimée",
    none: "Aucun jour de neige au sol sur la période.",
    // "Neige au sol 52 jours, dont 27 de suite du 2 au 28 février."
    cover: (days, longest, from, to) => {
      const count = days === 1 ? "1 jour" : `${days} jours`;
      if (days === 1) return `Neige au sol ${count}, le ${from}.`;
      if (longest === days) return `Neige au sol ${count}, du ${from} au ${to}.`;
      if (longest === 1) return `Neige au sol ${count}, jamais deux de suite.`;
      return `Neige au sol ${count}, dont ${longest} de suite du ${from} au ${to}.`;
    },
    method: (simulated) =>
      "La neige au sol n'est pas mesurée : elle est estimée à partir de la température moyenne et des " +
      "précipitations de chaque jour. Ce qui tombe par temps froid s'accumule, puis fond quand il dégèle. " +
      "Les dates sont justes à quelques jours près, moins bien en montagne. Les jours concernés ont " +
      "le bas de leur tuile en blanc sur le calendrier et un fond bleuté sur le graphique des précipitations." +
      (simulated
        ? " Pour une année simulée, c'est la neige d'un hiver possible du modèle, qui en donne un peu trop " +
          "en plaine : ce compte n'est pas celui du diagramme climatique, recalé sur le passé."
        : ""),
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
