from dataclasses import dataclass, field


@dataclass
class Resultado:
    numero: str | None = None
    fecha: str | None = None
    hora: str | None = None
    validez: str | None = None
    analista: str | None = None
    orden_trabajo: str | None = None
    id_muestra: str | None = None
    id_cliente: str | None = None
    ingreso: str | None = None
    humedad: str | None = None
    temperatura: str | None = None
    velocidad: str | None = None
    longitud_probeta: str | None = None
    diametro_probeta: str | None = None
    area: str | None = None
    modulo_young: str | None = None
    porcentaje_modulo: str | None = None
    reduccion_area: str | None = None
    carga_maxima: str | None = None
    deformacion_maxima: str | None = None
    esfuerzo_maximo: str | None = None
    elongacion_maxima: str | None = None
    deformacion_rotura: str | None = None
    esfuerzo_rotura: str | None = None
    elongacion_rotura: str | None = None
    carga_fluencia: str | None = None
    deformacion_fluencia: str | None = None
    esfuerzo_fluencia: str | None = None
    esfuerzo_limite_elastico: str | None = None
    rt_rf: str | None = None
    columnas_presentes: list[str] = field(default_factory=list, repr=False)

    COLUMNAS = dict(zip((
        "No", "Fecha", "Hora", "Validez", "Analista", "Orden trabajo",
        "ID muestra", "ID cliente", "Ingreso", "Humedad", "Temperatura (°C)",
        "Velocidad (MPa/s)", "Longitud probeta (mm)", "Diámetro probeta (mm)",
        "Área (mm²)", "Módulo de Young (MPa)", "Porcentaje módulo (%)",
        "Reducción área (%)", "Carga máxima (kN)", "Deformación máxima (mm)",
        "Esfuerzo máximo (MPa)", "Elongación máxima (%)",
        "Deformación en rotura (mm)", "Esfuerzo en rotura (MPa)",
        "Elongación en rotura (%)", "Carga en fluencia (N)",
        "Deformación en fluencia (mm)", "Esfuerzo en fluencia (MPa)",
        "Esfuerzo en límite elástico (MPa)", "RT_RF",
    ), (
        "numero", "fecha", "hora", "validez", "analista", "orden_trabajo",
        "id_muestra", "id_cliente", "ingreso", "humedad", "temperatura",
        "velocidad", "longitud_probeta", "diametro_probeta", "area",
        "modulo_young", "porcentaje_modulo", "reduccion_area", "carga_maxima",
        "deformacion_maxima", "esfuerzo_maximo", "elongacion_maxima",
        "deformacion_rotura", "esfuerzo_rotura", "elongacion_rotura",
        "carga_fluencia", "deformacion_fluencia", "esfuerzo_fluencia",
        "esfuerzo_limite_elastico", "rt_rf",
    )))

    @classmethod
    def desde_texto(cls, valores: dict[str, str | None]) -> "Resultado":
        return cls(**{cls.COLUMNAS[key]: value for key, value in valores.items()},
                   columnas_presentes=list(valores))

    def como_dict(self) -> dict[str, str | None]:
        return {key: getattr(self, self.COLUMNAS[key]) for key in self.columnas_presentes}


@dataclass
class ResultadoProcesado:
    resultado: Resultado
    avisos: list[str] = field(default_factory=list)
    campos_pendientes: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        return {
            "resultado": self.resultado.como_dict(),
            "campos_pendientes": self.campos_pendientes,
            "avisos": self.avisos,
        }
