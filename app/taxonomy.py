import os

import psycopg
from psycopg.rows import dict_row

ADMIN_DATABASE_URL = os.environ.get(
    "ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:55432/postgres"
)

SUBJECTS = {
    "PHY": {
        "name": "Physics",
        "chapters": {
            "Mechanics": [
                ("KIN", "Kinematics"),
                ("NLM", "Laws of Motion"),
                ("WEP", "Work, Energy and Power"),
                ("ROT", "Rotational Motion"),
                ("GRAV", "Gravitation"),
            ],
            "Properties of Matter and Waves": [
                ("FLU", "Fluid Mechanics"),
                ("THM", "Thermodynamics"),
                ("KTG", "Kinetic Theory of Gases"),
                ("OSC", "Oscillations"),
                ("WAV", "Waves"),
            ],
            "Electrodynamics": [
                ("ELS", "Electrostatics"),
                ("CEC", "Current Electricity"),
                ("MAG", "Moving Charges and Magnetism"),
                ("EMI", "Electromagnetic Induction"),
                ("ALT", "Alternating Current"),
            ],
            "Optics and Modern Physics": [
                ("RAY", "Ray Optics"),
                ("WOP", "Wave Optics"),
                ("MOD", "Modern Physics"),
                ("SEM", "Semiconductors"),
            ],
        },
    },
    "CHE": {
        "name": "Chemistry",
        "chapters": {
            "Physical Chemistry": [
                ("MOL", "Mole Concept and Stoichiometry"),
                ("ATO", "Atomic Structure"),
                ("BND", "Chemical Bonding"),
                ("THC", "Thermodynamics"),
                ("EQM", "Equilibrium"),
                ("RED", "Redox Reactions"),
                ("ELC", "Electrochemistry"),
                ("KIN", "Chemical Kinetics"),
                ("SOL", "Solutions"),
            ],
            "Inorganic Chemistry": [
                ("PER", "Periodic Table and Periodicity"),
                ("PBL", "p-Block Elements"),
                ("DBL", "d-Block Elements"),
                ("COO", "Coordination Compounds"),
            ],
            "Organic Chemistry": [
                ("GOC", "General Organic Chemistry"),
                ("HYD", "Hydrocarbons"),
                ("HAL", "Haloalkanes and Haloarenes"),
                ("ALD", "Aldehydes, Ketones and Acids"),
                ("BIOM", "Biomolecules"),
            ],
        },
    },
    "BIO": {
        "name": "Biology",
        "chapters": {
            "Cell and Genetics": [
                ("CEL", "Cell Structure and Function"),
                ("MOLB", "Biomolecules"),
                ("GEN", "Genetics and Inheritance"),
                ("EVO", "Evolution"),
            ],
            "Plant and Human Physiology": [
                ("PLP", "Plant Physiology"),
                ("HUP", "Human Physiology"),
                ("REP", "Reproduction"),
            ],
            "Ecology and Biotechnology": [
                ("ECO", "Ecology"),
                ("BTH", "Biotechnology"),
                ("HHD", "Human Health and Disease"),
            ],
        },
    },
}


def seed_taxonomy(exam="NEET", label="2026"):
    conn = psycopg.connect(ADMIN_DATABASE_URL, row_factory=dict_row)
    try:
        with conn.transaction():
            version = conn.execute(
                "select id from taxonomy_version where exam = %s and label = %s",
                (exam, label),
            ).fetchone()
            if version:
                return version["id"]
            version = conn.execute(
                "insert into taxonomy_version (exam, label, source_url, effective_from) "
                "values (%s, %s, %s, %s) returning id",
                (exam, label, "https://nta.ac.in", f"{label}-04-01"),
            ).fetchone()
            for subj_code, subj in SUBJECTS.items():
                subject = conn.execute(
                    "insert into subject (taxonomy_version_id, name, code) values (%s, %s, %s) returning id",
                    (version["id"], subj["name"], subj_code),
                ).fetchone()
                for ch_seq, (chapter_name, topics) in enumerate(subj["chapters"].items(), start=1):
                    chapter = conn.execute(
                        "insert into chapter (subject_id, name, code, sequence) values (%s, %s, %s, %s) returning id",
                        (subject["id"], chapter_name, f"{subj_code}-C{ch_seq}", ch_seq),
                    ).fetchone()
                    for t_seq, (code, name) in enumerate(topics, start=1):
                        conn.execute(
                            "insert into topic (chapter_id, name, code, sequence, difficulty_prior) "
                            "values (%s, %s, %s, %s, %s)",
                            (chapter["id"], name, code, t_seq, 0.5),
                        )
        return version["id"]
    finally:
        conn.close()


def topic_map(conn, exam="NEET", label="2026"):
    rows = conn.execute(
        """
        select t.id, t.code, t.name, s.id as subject_id, s.code as subject_code, c.name as chapter_name
        from topic t
        join chapter c on c.id = t.chapter_id
        join subject s on s.id = c.subject_id
        join taxonomy_version v on v.id = s.taxonomy_version_id
        where v.exam = %s and v.label = %s
        """,
        (exam, label),
    ).fetchall()
    return {r["code"]: r for r in rows}


if __name__ == "__main__":
    print(seed_taxonomy())
