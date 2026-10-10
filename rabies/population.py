"""Registered population (base population) of Prasat district, Surin.

Source: ทะเบียนราษฎร์ (สำนักทะเบียนกลาง กรมการปกครอง) — ข้อมูลเดือนกันยายน 2569
Columns = รวม (สัญชาติไทย + ไม่ใช่สัญชาติไทย): ชาย, หญิง, รวม
"""
import pandas as pd

POP_SOURCE = "ทะเบียนราษฎร์ กรมการปกครอง ข้อมูลเดือนกันยายน 2569"

# tambon: (male, female, total)
_POP = {
    "กังแอน": (4034, 4109, 8143),
    "ทมอ": (3086, 3387, 6473),
    "ไพล": (2668, 2826, 5494),
    "ปรือ": (4456, 4457, 8913),
    "ทุ่งมน": (3513, 3528, 7041),
    "ตาเบา": (4291, 4612, 8903),
    "หนองใหญ่": (5864, 5923, 11787),
    "โคกยาง": (6770, 7003, 13773),
    "โคกสะอาด": (5665, 5679, 11344),
    "บ้านไทร": (3135, 3198, 6333),
    "โชคนาสาม": (5677, 5759, 11436),
    "เชื้อเพลิง": (3756, 3998, 7754),
    "ปราสาททนง": (2636, 2699, 5335),
    "ตานี": (3581, 3688, 7269),
    "บ้านพลวง": (3947, 4050, 7997),
    "กันตวจระมวล": (2691, 2840, 5531),
    "สมุด": (1943, 2008, 3951),
    "ประทัดบุ": (2195, 2304, 4499),
}

POPULATION = pd.DataFrame(
    [(t, m, f, tot) for t, (m, f, tot) in _POP.items()],
    columns=["tambon", "pop_male", "pop_female", "pop_total"],
)

# integrity checks against the official totals row (69,908 / 72,068 / 141,976)
assert (POPULATION.pop_male + POPULATION.pop_female == POPULATION.pop_total).all()
assert POPULATION.pop_total.sum() == 141_976 and POPULATION.pop_male.sum() == 69_908


def base_population(tambons=None) -> int:
    """Registered population of the selected tambons (all if none selected)."""
    p = POPULATION if not tambons else POPULATION[POPULATION.tambon.isin(tambons)]
    return int(p.pop_total.sum())
