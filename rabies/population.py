"""Registered base population and houses of Prasat district, Surin.

Source: ทะเบียนราษฎร์ (สำนักทะเบียนกลาง กรมการปกครอง) — ข้อมูลเดือนกันยายน 2569
- Population = รวม (สัญชาติไทย + ไม่ใช่สัญชาติไทย): ชาย, หญิง, รวม
- Houses     = สถิติจำนวนบ้าน (หลัง)
"""
import pandas as pd

POP_SOURCE = "ทะเบียนราษฎร์ กรมการปกครอง ข้อมูลเดือนกันยายน 2569"

# tambon: (male, female, total population, houses)
_POP = {
    "กังแอน": (4034, 4109, 8143, 3321),
    "ทมอ": (3086, 3387, 6473, 2074),
    "ไพล": (2668, 2826, 5494, 1696),
    "ปรือ": (4456, 4457, 8913, 2936),
    "ทุ่งมน": (3513, 3528, 7041, 1950),
    "ตาเบา": (4291, 4612, 8903, 2767),
    "หนองใหญ่": (5864, 5923, 11787, 3520),
    "โคกยาง": (6770, 7003, 13773, 4233),
    "โคกสะอาด": (5665, 5679, 11344, 3366),
    "บ้านไทร": (3135, 3198, 6333, 1983),
    "โชคนาสาม": (5677, 5759, 11436, 3371),
    "เชื้อเพลิง": (3756, 3998, 7754, 2604),
    "ปราสาททนง": (2636, 2699, 5335, 1740),
    "ตานี": (3581, 3688, 7269, 2085),
    "บ้านพลวง": (3947, 4050, 7997, 3177),
    "กันตวจระมวล": (2691, 2840, 5531, 1709),
    "สมุด": (1943, 2008, 3951, 1281),
    "ประทัดบุ": (2195, 2304, 4499, 1395),
}

POPULATION = pd.DataFrame(
    [(t, *v) for t, v in _POP.items()],
    columns=["tambon", "pop_male", "pop_female", "pop_total", "houses_total"],
)
POPULATION["persons_per_house"] = (POPULATION.pop_total / POPULATION.houses_total).round(2)

# integrity checks against the official totals rows
assert (POPULATION.pop_male + POPULATION.pop_female == POPULATION.pop_total).all()
assert POPULATION.pop_total.sum() == 141_976 and POPULATION.pop_male.sum() == 69_908
assert POPULATION.houses_total.sum() == 45_208


def _sel(tambons):
    return POPULATION if not tambons else POPULATION[POPULATION.tambon.isin(tambons)]


def base_population(tambons=None) -> int:
    """Registered population of the selected tambons (all if none selected)."""
    return int(_sel(tambons).pop_total.sum())


def base_houses(tambons=None) -> int:
    """Registered houses of the selected tambons (all if none selected)."""
    return int(_sel(tambons).houses_total.sum())
