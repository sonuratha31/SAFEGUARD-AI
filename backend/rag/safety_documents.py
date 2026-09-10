"""
SAFEGUARD AI - Safety Standard Documents
Embedded safety knowledge base for use when no external documents are available.
These represent well-known industrial safety standards.
"""

SAFETY_DOCUMENTS = [
    {
        "doc_id": "ISO-13849-1",
        "title": "ISO 13849-1: Safety of Machinery - Safety-Related Parts of Control Systems",
        "document_type": "standard",
        "source": "ISO 13849-1:2015",
        "machine_categories": ["cnc_machine", "hydraulic_press", "industrial_motor", "compressor", "conveyor"],
        "topics": ["safety_controls", "guards", "interlocks", "emergency_stop"],
        "version": "2015",
        "chunks": [
            {
                "section": "4.1 General Requirements",
                "topic": "safety_controls",
                "content": (
                    "Safety-related parts of control systems shall be designed, constructed, "
                    "selected, assembled and combined in accordance with this part of ISO 13849, "
                    "so that they can perform their intended safety functions. The safety function "
                    "shall be maintained throughout the life of the machine."
                ),
            },
            {
                "section": "5.1 Guard Requirements",
                "topic": "guards",
                "content": (
                    "Guards shall be designed and constructed to prevent access to hazardous zones "
                    "during operation. Fixed guards shall require a tool to remove them. "
                    "Interlocked guards shall cause a stop function when opened. "
                    "Guards shall be of robust construction and firmly secured in place."
                ),
            },
            {
                "section": "5.2 Interlock Devices",
                "topic": "interlocks",
                "content": (
                    "Interlocking guards shall be connected to the control system so that the "
                    "machine cannot operate when the guard is open. The interlock function shall "
                    "be monitored. Failure of the interlock circuit shall result in a safe state. "
                    "Position switches used as interlocks shall be positively actuated."
                ),
            },
            {
                "section": "5.3 Emergency Stop",
                "topic": "emergency_stop",
                "content": (
                    "Emergency stop devices shall be readily accessible. "
                    "They shall be clearly identifiable—red actuator on yellow background. "
                    "Activation shall initiate a stop function of the appropriate stop category. "
                    "The emergency stop function shall remain latched until manually reset."
                ),
            },
        ],
    },
    {
        "doc_id": "ISO-13857",
        "title": "ISO 13857: Safety of Machinery - Safety Distances",
        "document_type": "standard",
        "source": "ISO 13857:2019",
        "machine_categories": ["cnc_machine", "hydraulic_press", "conveyor"],
        "topics": ["safety_distances", "guards", "hazardous_zones"],
        "version": "2019",
        "chunks": [
            {
                "section": "4 Safety Distances for Upper Limbs",
                "topic": "safety_distances",
                "content": (
                    "Safety distances shall prevent the upper limbs from reaching hazardous zones. "
                    "For openings in guards, the minimum safety distance is determined by the "
                    "opening size. For a square opening of 4mm the safety distance is 10mm. "
                    "Openings larger than 120mm require a safety distance of 850mm or more."
                ),
            },
        ],
    },
    {
        "doc_id": "OSHA-1910.212",
        "title": "OSHA 1910.212: General Requirements for All Machines",
        "document_type": "regulation",
        "source": "OSHA 29 CFR 1910.212",
        "machine_categories": ["cnc_machine", "hydraulic_press", "industrial_motor", "compressor", "conveyor"],
        "topics": ["machine_guards", "point_of_operation", "maintenance"],
        "version": "current",
        "chunks": [
            {
                "section": "1910.212(a)(1) Machine Guarding",
                "topic": "machine_guards",
                "content": (
                    "One or more methods of machine guarding shall be provided to protect the operator "
                    "and other employees in the machine area from hazards such as those created by "
                    "point of operation, ingoing nip points, rotating parts, flying chips and sparks. "
                    "Examples of guarding methods are: barrier guards, two-hand tripping devices, "
                    "electronic safety devices, etc."
                ),
            },
            {
                "section": "1910.212(a)(3) Point of Operation Guarding",
                "topic": "point_of_operation",
                "content": (
                    "Point of operation is the area on a machine where work is actually performed. "
                    "The point of operation of machines whose operation exposes an employee to injury "
                    "shall be guarded. The guarding device shall be in conformity with any appropriate "
                    "standards therefor, or, in the absence of applicable specific standards, shall be "
                    "so designed and constructed as to prevent the operator from having any part of his "
                    "body in the danger zone during the operating cycle."
                ),
            },
            {
                "section": "1910.212(b) Anchoring Fixed Machinery",
                "topic": "machine_guards",
                "content": (
                    "Machines designed for a fixed location shall be securely anchored to prevent "
                    "walking or moving. This requirement applies to all machines that could create "
                    "hazards by movement during operation."
                ),
            },
        ],
    },
    {
        "doc_id": "OSHA-1910.217",
        "title": "OSHA 1910.217: Mechanical Power Presses",
        "document_type": "regulation",
        "source": "OSHA 29 CFR 1910.217",
        "machine_categories": ["hydraulic_press"],
        "topics": ["press_safety", "guards", "maintenance"],
        "version": "current",
        "chunks": [
            {
                "section": "1910.217(b)(1) Guard Requirements for Presses",
                "topic": "press_safety",
                "content": (
                    "Every press shall be equipped with a point of operation guard or properly applied "
                    "and adjusted point of operation device. The guard shall prevent entry of hands or "
                    "fingers into the point of operation. The guard shall be secured to the press frame."
                ),
            },
            {
                "section": "1910.217(e) Inspection and Maintenance",
                "topic": "maintenance",
                "content": (
                    "Each press shall be inspected and tested at regular intervals to ensure compliance "
                    "with all requirements. A record of each inspection and test shall be maintained. "
                    "Any safety-critical defects shall be corrected before resumption of operations."
                ),
            },
        ],
    },
    {
        "doc_id": "ISO-4413",
        "title": "ISO 4413: Hydraulic Fluid Power - General Rules",
        "document_type": "standard",
        "source": "ISO 4413:2010",
        "machine_categories": ["hydraulic_press"],
        "topics": ["hydraulic_pressure", "temperature", "maintenance"],
        "version": "2010",
        "chunks": [
            {
                "section": "5.4 Pressure Limiting",
                "topic": "hydraulic_pressure",
                "content": (
                    "Every hydraulic system shall be protected by at least one pressure relief valve. "
                    "The relief valve shall be set to limit pressure to a safe working level. "
                    "The maximum working pressure shall be clearly marked on the machine. "
                    "Pressure gauges shall be provided to monitor system pressure."
                ),
            },
            {
                "section": "5.5 Temperature Control",
                "topic": "temperature",
                "content": (
                    "Hydraulic fluid temperature shall be maintained within the range specified by the "
                    "fluid manufacturer. Excessive temperature reduces viscosity and accelerates fluid "
                    "degradation. Cooling shall be provided where necessary. Temperature shall be "
                    "monitored and an alarm provided if the limit is exceeded."
                ),
            },
        ],
    },
    {
        "doc_id": "IEC-60079-14",
        "title": "IEC 60079-14: Explosive Atmospheres - Electrical Installations",
        "document_type": "standard",
        "source": "IEC 60079-14:2013",
        "machine_categories": ["compressor", "industrial_motor"],
        "topics": ["temperature", "electrical_safety"],
        "version": "2013",
        "chunks": [
            {
                "section": "6.1 Temperature Classification",
                "topic": "temperature",
                "content": (
                    "Electrical equipment operating in potentially explosive atmospheres shall not "
                    "exceed the ignition temperature of the surrounding atmosphere. Temperature class "
                    "T1 allows surface temperatures up to 450°C, T2 up to 300°C, T3 up to 200°C, "
                    "T4 up to 135°C, T5 up to 100°C, T6 up to 85°C. Motors shall be selected with "
                    "temperature class appropriate to the hazardous area classification."
                ),
            },
        ],
    },
    {
        "doc_id": "ISO-10816-3",
        "title": "ISO 10816-3: Mechanical Vibration - Evaluation Criteria",
        "document_type": "standard",
        "source": "ISO 10816-3:2009",
        "machine_categories": ["cnc_machine", "industrial_motor", "compressor", "conveyor"],
        "topics": ["vibration", "maintenance"],
        "version": "2009",
        "chunks": [
            {
                "section": "Table 1: Vibration Zones",
                "topic": "vibration",
                "content": (
                    "Zone A (0–2.3 mm/s RMS): Newly commissioned machines, considered acceptable. "
                    "Zone B (2.3–4.5 mm/s RMS): Machines with long-term unrestricted operation. "
                    "Zone C (4.5–7.1 mm/s RMS): Unsatisfactory for long-term operation, short-term only. "
                    "Zone D (>7.1 mm/s RMS): Vibration values in this zone are considered to be of "
                    "sufficient severity to cause damage to the machine. Immediate shutdown recommended."
                ),
            },
            {
                "section": "4.2 Measurement Parameters",
                "topic": "vibration",
                "content": (
                    "Vibration velocity (RMS) in mm/s is the recommended measurement parameter for "
                    "evaluating machine vibration. Measurements shall be taken at bearing housings "
                    "in three mutually perpendicular directions. The highest measured value shall be "
                    "used for comparison against the zone boundaries."
                ),
            },
        ],
    },
    {
        "doc_id": "NFPA-79",
        "title": "NFPA 79: Electrical Standard for Industrial Machinery",
        "document_type": "standard",
        "source": "NFPA 79:2021",
        "machine_categories": ["cnc_machine", "hydraulic_press", "industrial_motor", "compressor", "conveyor"],
        "topics": ["electrical_safety", "emergency_stop", "maintenance"],
        "version": "2021",
        "chunks": [
            {
                "section": "9.2 Emergency Stop",
                "topic": "emergency_stop",
                "content": (
                    "Emergency stop shall stop the motion of the machine in the quickest possible time "
                    "without creating other hazards. Category 0 (immediate power removal), "
                    "Category 1 (controlled stop then power removal), or Category 2 (controlled stop "
                    "with power maintained) shall be selected based on risk assessment. "
                    "Emergency stop devices shall be self-monitoring."
                ),
            },
            {
                "section": "12.5 Maintenance",
                "topic": "maintenance",
                "content": (
                    "Machines shall be maintained in accordance with the manufacturer's recommendations. "
                    "Maintenance records shall be kept. Lockout/tagout procedures shall be followed "
                    "before any maintenance activity. The electrical supply shall be disconnected and "
                    "locked before work on the machine."
                ),
            },
            {
                "section": "9.1 Protective Devices",
                "topic": "electrical_safety",
                "content": (
                    "Machines shall be provided with overcurrent protection for all circuit conductors. "
                    "Ground fault protection shall be provided for circuits operating at more than 150V. "
                    "All protective devices shall be accessible and clearly labelled."
                ),
            },
        ],
    },
    {
        "doc_id": "ISO-4414",
        "title": "ISO 4414: Pneumatic Fluid Power - General Rules",
        "document_type": "standard",
        "source": "ISO 4414:2010",
        "machine_categories": ["compressor", "cnc_machine"],
        "topics": ["pneumatic_pressure", "temperature", "maintenance"],
        "version": "2010",
        "chunks": [
            {
                "section": "5.3 Pressure Safety",
                "topic": "pneumatic_pressure",
                "content": (
                    "All pneumatic systems shall be equipped with safety relief valves set at or below "
                    "the maximum allowable working pressure (MAWP). Pressure vessels shall be designed, "
                    "constructed, and marked in accordance with applicable pressure vessel standards. "
                    "The maximum working pressure shall not exceed the design pressure."
                ),
            },
        ],
    },
    {
        "doc_id": "CONVEYOR-SAFETY-GUIDE",
        "title": "CEMA Safety Guidelines for Belt Conveyors",
        "document_type": "guideline",
        "source": "CEMA Safety Best Practices",
        "machine_categories": ["conveyor"],
        "topics": ["guards", "maintenance", "emergency_stop", "load"],
        "version": "current",
        "chunks": [
            {
                "section": "Section 3: Nip Point Guards",
                "topic": "guards",
                "content": (
                    "All nip points, including head and tail pulleys, shall be guarded. "
                    "Guards shall be designed so they cannot be removed without tools and "
                    "shall be replaced before operation resumes. The guard shall prevent "
                    "contact with the nip point from all practicable directions."
                ),
            },
            {
                "section": "Section 6: Belt Loading",
                "topic": "load",
                "content": (
                    "Conveyor belts shall not be loaded beyond their rated carrying capacity. "
                    "Overloading causes premature belt wear, overheating of drive motors, and "
                    "increased risk of belt failure. Load monitoring systems are recommended "
                    "for high-capacity installations."
                ),
            },
        ],
    },
]
