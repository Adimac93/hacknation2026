// SAMPLE DATA ONLY. The preview has no access to registers or COI dictionaries, so it
// shows small, made-up sets. Nothing here is real data or a complete dictionary.

/** Sample values for `defaultValueType: "EXTERNAL_SYSTEM"` attributes, by source. */
export const SAMPLE_REGISTERS: Record<string, Record<string, string>> = {
  PESEL: {
    pesel: "51051101608",
    name: "JAN",
    secondName: "PIOTR",
    surname: "NOWAK",
    birthDate: "1951-05-11",
    citizenship: "polskie",
    birthPlace: "Elbląg",
    birthCountry: "Polska",
    sex: "mężczyzna",
    motherName: "ANNA",
    fatherName: "ADAM",
    familyName: "NOWAK",
  },
  PESEL_ADDRESS: {
    permanentAddressVoivodeship: "warmińsko-mazurskie",
    permanentAddressCommunity: "Elbląg",
    permanentAddressPlace: "Elbląg",
    permanentAddressStreet: "Polna",
    permanentAddressHouseNumber: "1",
    permanentAddressApartmentNumber: "2",
    permanentAddressPostalCode: "82-300",
  },
  MLPZ: {
    name: "JAN",
    secondName: "PIOTR",
    surname: "NOWAK",
    pesel: "51051101608",
    phoneNumber: "+48123456789",
    email: "jan.nowak@mail.pl",
    country: "Polska",
    voivodeship: "warmińsko-mazurskie",
    community: "Elbląg",
    place: "Elbląg",
    postCode: "82-300",
    street: "Polna",
    building: "1",
    apartment: "2",
  },
};

/** Returns the sample value for e.g. `MLPZ.name`; empty when the source lacks it. */
export function sampleRegisterValue(reference: string): string {
  const [source = "", attribute = ""] = reference.split(".", 2);
  return SAMPLE_REGISTERS[source]?.[attribute] ?? "";
}

export interface SampleDictionary {
  /** Field label to show when the field title is just the dictionary name. */
  label: string;
  entries: string[];
}

const VOIVODESHIPS = [
  "dolnośląskie",
  "kujawsko-pomorskie",
  "lubelskie",
  "lubuskie",
  "łódzkie",
  "małopolskie",
  "mazowieckie",
  "opolskie",
  "podkarpackie",
  "podlaskie",
  "pomorskie",
  "śląskie",
  "świętokrzyskie",
  "warmińsko-mazurskie",
  "wielkopolskie",
  "zachodniopomorskie",
];

const VOIVODESHIP_DICTIONARY: SampleDictionary = { label: "Województwo", entries: VOIVODESHIPS };

const DICTIONARIES: Record<string, SampleDictionary> = {
  kraje: {
    label: "Kraj",
    entries: [
      "Polska",
      "Austria",
      "Belgia",
      "Białoruś",
      "Czechy",
      "Dania",
      "Francja",
      "Hiszpania",
      "Holandia",
      "Irlandia",
      "Litwa",
      "Łotwa",
      "Niemcy",
      "Norwegia",
      "Słowacja",
      "Szwecja",
      "Ukraina",
      "Wielka Brytania",
      "Włochy",
    ],
  },
  teryt_dowodowy: VOIVODESHIP_DICTIONARY,
  teryt_4g_dowodowy: VOIVODESHIP_DICTIONARY,
  województwo: VOIVODESHIP_DICTIONARY,
  powiat: {
    label: "Powiat",
    entries: ["elbląski", "Elbląg", "braniewski", "malborski", "nowodworski", "ostródzki"],
  },
  gmina: {
    label: "Gmina",
    entries: ["Elbląg", "Gronowo Elbląskie", "Milejewo", "Młynary", "Pasłęk", "Tolkmicko"],
  },
  miejscowość: {
    label: "Miejscowość",
    entries: ["Elbląg", "Pasłęk", "Tolkmicko", "Młynary", "Milejewo"],
  },
  "numery kierunkowe": {
    label: "Numer kierunkowy",
    entries: [
      "+48 Polska",
      "+49 Niemcy",
      "+420 Czechy",
      "+421 Słowacja",
      "+370 Litwa",
      "+380 Ukraina",
    ],
  },
};

export function sampleDictionary(name: string | undefined): SampleDictionary | undefined {
  if (!name) return undefined;
  return DICTIONARIES[name.trim().toLowerCase()];
}
