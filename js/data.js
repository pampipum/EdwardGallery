const WURSTER_WORKS = [
  '1976A104_Olivenplantage bei Hammameth',
  '1976A108_Stillleben',
  '1979A076_Vollmond',
  '1979A087_San Remo by Night',
  '1979A113_Stillleben mit Krug',
  '1979oe038_Roter Tisch',
  '1979oe047_Provence',
  '1980A078_Morgenwolken',
  '1980A079_Rigi Nebelmeer',
  '1980A100_Buendner Alpen',
  '1981A096_Im Sottoceneri',
  '1981A102_Seepark in Lugano',
  '1981A114_Bei Lugano',
  '1981oe027_Interieur mit weisser Kommode',
  '1981oe041_Postplatz Zwischensaison',
  '1982A068_Herbstastern',
  '1982A078_Maerchenbaeume',
  '1982A079_Kleines Straeusschen',
  '1982A098_Maerchenwald',
  '1982A107_Thurg.Schaffh.Heilstaette',
  '1982A118_Stillleben',
  '1982oe035_Interieur Postatelier',
  '1983A052_Villagio Treinese',
  '1983A068_Haeuser im Abendsonnenschein',
  '1983A081_Landschaft mit Sonnenball'
];

export const HALL_CONFIG = {
  width: 14,
  height: 6,
  length: 96,
  spawnPosition: { x: 0, y: 1.72, z: 24 }
};

export const EXPERIENCE_CONFIG = {
  playerRadius: 0.36,
  playerSpeed: 24.3,
  interactDistance: 3.6,
  maxDeltaTime: 0.05
};

function parseWorkLabel(raw, index) {
  const yearMatch = raw.match(/^(\d{4})/);
  const title = raw.replace(/^[0-9]{4}[A-Za-z0-9]+_/, '').replace(/_/g, ' ');
  const year = yearMatch ? yearMatch[1] : 'Unknown';

  const statusCycle = ['available', 'available', 'reserved', 'sold'];

  return {
    id: `work-${index + 1}`,
    title,
    year,
    status: statusCycle[index % statusCycle.length],
    description: `Edward Wurster, ${year === 'Unknown' ? 'unknown year' : year} study from the Davos-era collection.`,
    texturePath: `./assets/wurster/wurster-${String(index + 1).padStart(2, '0')}.jpg`
  };
}

export const PAINTINGS = WURSTER_WORKS.map(parseWorkLabel);

export const BIOGRAPHY_CONTENT = {
  intro:
    'Die handwerkliche Grundlage und den Umgang mit der Farbe hat Eduard Wurster bei Albert Pfister erworben. Früh fand er jedoch seine eigene Ausdrucksweise. Seine Werke sollen direkt wirken und nicht überanalysiert werden.',
  timeline: [
    {
      period: '1927 - 1942',
      title: 'Jugend und frühe Malversuche',
      text: 'Geboren am 7. September 1927 in Küsnacht (ZH). Bereits in der Schulzeit erste Kopien und Naturstudien in Aquarell und Öl.'
    },
    {
      period: '1942 - 1953',
      title: 'Anfänge',
      text: 'Eigenständige Versuche nach der Natur. Früh geprägt von Zürcher Malern wie Kündig, Gubler, Morgenthaler und Gimmi.'
    },
    {
      period: '1947 - 1949',
      title: 'Tuberkulose und Davos-Weichenstellung',
      text: 'Diagnose Lungentuberkulose während der Rekrutenschule. Längere Kur in Davos Clavadel, danach Empfehlung, in Davos zu bleiben.'
    },
    {
      period: 'ab 1949',
      title: 'Postamt Davos und frühe Ausstellungen',
      text: 'Dienst beim Postamt Davos Platz. Wegen engem Wohnraum Fokus auf Aquarelle. 1950 erste Ausstellungserfolge mit Bildverkauf.'
    },
    {
      period: '1954 - 1960',
      title: 'Lehrjahre und Albert Pfister',
      text: 'Über Gerhard Ahnfeldt vertiefte Kontakte mit Albert Pfister. Intensive Studien zu Farbe, Licht und Komposition, parallel autodidaktisches Studium der europäischen Moderne.'
    },
    {
      period: '1960 - 1979',
      title: 'Bruch und Dunkle Periode',
      text: 'Trennung von Pfister, bewusste Loslösung. Experimentieren mit Schwarz und gedämpften Tonwerten in der Ölmalerei, während die Aquarelle eigenständig weiterliefen.'
    },
    {
      period: '1979 - 1985',
      title: 'Neubeginn nach Herzkrankheit',
      text: 'Nach gesundheitlichem Einschnitt Neustart mit den Grundfarben Rot, Blau und Gelb im ehemaligen Telefonzentralraum Davos.'
    },
    {
      period: 'ab ca. 1985',
      title: 'Eigene Malerei',
      text: 'Wurster beschreibt seine Handschrift als figurativ-abstrakt. Farbe und Komposition tragen die Aussage, nicht die reine Naturabbildung.'
    },
    {
      period: '1994 - 1997',
      title: 'Krise und Schaffenspause',
      text: 'Künstlerische Sackgasse, einjährige Pause 1996/97. Danach mutiger Neustart ohne starre Erwartungen.'
    },
    {
      period: 'ab 1997',
      title: 'Innen/Aussen-Phase',
      text: 'Aufbrechen des klassischen Bildrahmens. Interieur und Landschaft greifen ineinander, der Raum selbst wird Teil des Bildes.'
    },
    {
      period: '2003',
      title: 'Anerkennung in Davos',
      text: 'Drei Gemälde werden von der Kunstkommission der Landschaft Davos gekauft und im Rathaus Davos platziert.'
    }
  ],
  sources: [
    'https://wurster-kunst.ch/pages/biografie.html',
    'https://wurster-kunst.ch/pages/biografie_01.html',
    'https://wurster-kunst.ch/pages/biografie_02.html',
    'https://wurster-kunst.ch/pages/werdegang_jugendzeit.html',
    'https://wurster-kunst.ch/pages/werdegang_anfaenge.html',
    'https://wurster-kunst.ch/pages/werdegang_lehrjahre.html',
    'https://wurster-kunst.ch/pages/werdegang_bruch.html',
    'https://wurster-kunst.ch/pages/werdegang_neubeginn.html',
    'https://wurster-kunst.ch/pages/werdegang_eigene.html'
  ]
};

export const HDRI_PATH = './assets/hdri/davos_alps_1k.hdr';
