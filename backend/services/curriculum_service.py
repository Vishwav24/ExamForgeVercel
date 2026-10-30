"""
Tamil Nadu State Board (Samacheer Kalvi) Curriculum Service
Provides verified classes (6-12), subjects, and textbook chapters.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import SessionLocal
from database.models import Curriculum, Question

# Verified Tamil Nadu State Board Classes
TN_CLASSES = [
    'Class 6',
    'Class 7',
    'Class 8',
    'Class 9',
    'Class 10',
    'Class 11',
    'Class 12'
]

# Verified Curriculum Registry: Class -> Subject -> Chapters
TN_CURRICULUM_DATA = {
    'Class 6': {
        'Mathematics': [
            'Numbers', 'Introduction to Algebra', 'Ratio and Proportion',
            'Geometry', 'Statistics', 'Information Processing'
        ],
        'Science': [
            'Measurements', 'Force and Motion', 'Matter Around Us',
            'The Living World of Plants', 'Living World of Animals',
            'Health and Hygiene', 'Electricity', 'Changes Around Us',
            'Air', 'The Cell', 'Human Organ Systems'
        ],
        'Social Science': [
            'What is History?', 'On the Trail of the Earliest People',
            'The Earth and Solar System', 'Land and Oceans',
            'Understanding Diversity', 'Achieving Equality', 'From Chiefdoms to Empires'
        ],
        'English': [
            'Sea Turtles', 'When the Trees Walked', 'A Visitor from Distant Lands',
            'The Crocodile', 'Trees'
        ],
        'Tamil': [
            'இன்பத்தமிழ்', 'தமிழ் கும்மி', 'கனவு பலித்தது',
            'சிலப்பதிகாரம்', 'காணி நிலம்', 'சிறகின் ஓசை', 'அறிவியல் ஆத்திசூடி'
        ]
    },
    'Class 7': {
        'Mathematics': [
            'Number System and Integers', 'Fractions and Decimals', 'Algebra',
            'Direct and Inverse Proportion', 'Geometry', 'Information Processing'
        ],
        'Science': [
            'Measurement', 'Force and Motion', 'Matter Around Us',
            'Atomic Structure', 'Reproduction and Modification in Plants',
            'Health and Hygiene', 'Light', 'Electricity'
        ],
        'Social Science': [
            'Sources of Medieval India', 'Emergence of New Kingdoms in North India',
            'The Delhi Sultanate', 'The Mughal Empire', 'Interior of the Earth',
            'Landforms', 'Women Rights'
        ],
        'English': [
            'Eidgah', 'The Wind on Haunted Hill', 'A Prayer to the Teacher',
            'The Listeners', 'Your Space'
        ],
        'Tamil': [
            'எங்கள் தமிழ்', 'ஒன்றல்ல இரண்டல்ல', 'காடு',
            'அப்படியே நிற்கட்டும் அந்த மரம்', 'புலி தங்கிய குகை'
        ]
    },
    'Class 8': {
        'Mathematics': [
            'Rational Numbers', 'Measurements', 'Algebra',
            'Life Mathematics', 'Geometry', 'Statistics', 'Information Processing'
        ],
        'Science': [
            'Measurement', 'Force and Pressure', 'Light', 'Heat',
            'Electricity', 'Sound', 'Magnetism', 'Universe and Space Science',
            'Matter Around Us', 'Changes Around Us', 'Air', 'Atomic Structure',
            'Microorganisms', 'Plant Kingdom', 'Human Anatomy'
        ],
        'Social Science': [
            'Advent of the Europeans', 'From Trade to Territory', 'Rural Life and Society',
            'Peoples Revolt', 'Educational Development in India', 'Development of Industries',
            'Rocks and Soils', 'Weather and Climate'
        ],
        'English': [
            'The Nose-Jewel', 'Hobby Turns into a Successful Career', 'Sir Isaac Newton',
            'Special Hero', 'My Hobby: Reading'
        ],
        'Tamil': [
            'தமிழ்மொழி வாழ்த்து', 'தமிழ்மொழி மரபு', 'ஓடை',
            'கோணக் காத்துப்பாட்டு', 'நோயும் மருந்தும்'
        ]
    },
    'Class 9': {
        'Mathematics': [
            'Set Language', 'Real Numbers', 'Algebra', 'Coordinate Geometry',
            'Geometry', 'Trigonometry', 'Mensuration', 'Statistics', 'Probability'
        ],
        'Science': [
            'Measurement', 'Motion', 'Fluids', 'Electric Charge and Electric Current',
            'Light', 'Heat', 'Sound', 'Magnetism and Electromagnetism', 'Universe',
            'Matter Around Us', 'Atomic Structure', 'Periodic Classification of Elements',
            'Chemical Bonding', 'Acids Bases and Salts', 'Carbon and its Compounds',
            'Organization of Tissues', 'Plant Physiology', 'Animal Kingdom'
        ],
        'Social Science': [
            'Evolution of Humans and Society', 'Early Civilizations',
            'State and Society in Medieval Times', 'Intellectual Awakening and Socio-Political Changes',
            'Lithosphere', 'Atmosphere', 'Hydrosphere', 'Forms of Government and Democracy'
        ],
        'English': [
            'The Fun They Had', 'The Sound of Music', 'The Little Girl',
            'A Truly Beautiful Mind', 'The Snake and the Mirror'
        ],
        'Tamil': [
            'திராவிட மொழிக்குடும்பம்', 'தமிழோவியம்', 'பெரியார் சிந்தனைகள்',
            'பட்டமரம்', 'பெரியபுராணம்'
        ]
    },
    'Class 10': {
        'Mathematics': [
            'Relations and Functions', 'Numbers and Sequences', 'Algebra',
            'Geometry', 'Coordinate Geometry', 'Trigonometry', 'Mensuration',
            'Statistics and Probability'
        ],
        'Science': [
            'Laws of Motion', 'Optics', 'Thermal Physics', 'Electricity',
            'Acoustics', 'Nuclear Physics', 'Atoms and Molecules',
            'Periodic Classification of Elements', 'Solutions',
            'Types of Chemical Reactions', 'Carbon and its Compounds',
            'Plant Anatomy and Plant Physiology', 'Structural Organisation of Animals',
            'Transportation in Plants and Circulation in Animals', 'Nervous System',
            'Plant and Animal Hormones', 'Reproduction in Plants and Animals',
            'Heredity', 'Origin and Evolution of Life', 'Breeding and Biotechnology',
            'Environmental Management'
        ],
        'Social Science': [
            'Outbreak of World War I and its Aftermath', 'The World between two World Wars',
            'World War II', 'India - Location Relief and Drainage',
            'Climate and Natural Vegetation of India', 'Agriculture', 'Resources and Industries',
            'Indian Constitution', 'Central Government', 'State Government',
            'Gross Domestic Product and its Growth'
        ],
        'English': [
            'His First Flight', 'The Night the Ghost Got In', 'Empowered Women Navigating The World',
            'The Attic', 'Life', 'The Secret of the Machines'
        ],
        'Tamil': [
            'அன்னை மொழியே', 'தமிழ்ச்சொல் வளம்', 'காற்றே வா',
            'முல்லைப்பாட்டு', 'திருக்குறள்', 'காலக்கணிதம்'
        ]
    },
    'Class 11': {
        'Physics': [
            'Nature of Physical World and Measurement', 'Kinematics', 'Laws of Motion',
            'Work Energy and Power', 'Motion of System of Particles and Rigid Bodies',
            'Gravitation', 'Properties of Matter', 'Heat and Thermodynamics',
            'Kinetic Theory of Gases', 'Oscillations', 'Waves'
        ],
        'Chemistry': [
            'Basic Concepts of Chemistry and Chemical Calculations',
            'Quantum Mechanical Model of Atom', 'Periodic Classification of Elements',
            'Hydrogen', 'Alkali and Alkaline Earth Metals', 'Gaseous State',
            'Thermodynamics', 'Physical and Chemical Equilibrium', 'Solutions',
            'Chemical Bonding', 'Organic Chemistry Fundamentals'
        ],
        'Mathematics': [
            'Sets Relations and Functions', 'Basic Algebra', 'Trigonometry',
            'Combinatorics and Mathematical Induction', 'Binomial Theorem Sequences and Series',
            'Two Dimensional Analytical Geometry', 'Matrices and Determinants',
            'Vector Algebra', 'Differential Calculus', 'Integral Calculus', 'Probability Theory'
        ],
        'Biology': [
            'Living World', 'Plant Kingdom', 'Animal Kingdom',
            'Cell Structure and Function', 'Biomolecules', 'Plant Physiology', 'Human Physiology'
        ],
        'Computer Science': [
            'Introduction to Computers', 'Number Systems', 'Computer Organization',
            'Theoretical Concepts of Operating System', 'Working with Windows OS',
            'Specification and Abstraction', 'Composition and Decomposition',
            'Iteration and Recursion', 'Introduction to C++', 'Control Statements',
            'Functions', 'Arrays and Structures', 'Object Oriented Concepts'
        ],
        'Commerce': [
            'Historical Background of Commerce', 'Objectives of Business',
            'Forms of Business Organisation', 'Sole Proprietorship', 'Partnership',
            'Joint Stock Company', 'Cooperative Organisations'
        ],
        'Accountancy': [
            'Introduction to Accounting', 'Conceptual Framework of Accounting',
            'Books of Prime Entry', 'Ledger', 'Trial Balance', 'Bank Reconciliation Statement'
        ],
        'Economics': [
            'Introduction to Microeconomics', 'Consumption Analysis', 'Production Analysis',
            'Cost and Revenue Analysis', 'Market Structure and Pricing', 'Tamil Nadu Economy'
        ],
        'English': [
            'The Portrait of a Lady', 'We are not Afraid to Die', 'Discovering Tut',
            'The Ailing Planet', 'The Browning Version'
        ],
        'Tamil': [
            'யுகத்தின் பாடல்', 'பேச்சுமொழியும் கவிதைமொழியும்', 'இயற்கை வேளாண்மை',
            'காவியத் தலைவன்', 'புரட்சிக்கவி'
        ]
    },
    'Class 12': {
        'Physics': [
            'Electrostatics', 'Current Electricity', 'Magnetism and Magnetic Effects of Electric Current',
            'Electromagnetic Induction and Alternating Current', 'Electromagnetic Waves',
            'Optics', 'Dual Nature of Radiation and Matter', 'Atomic and Nuclear Physics',
            'Semiconductor Electronics', 'Communication Systems'
        ],
        'Chemistry': [
            'Metallurgy', 'p-Block Elements-I', 'p-Block Elements-II',
            'Transition and Inner Transition Elements', 'Coordination Chemistry',
            'Solid State', 'Chemical Kinetics', 'Ionic Equilibrium',
            'Electrochemistry', 'Surface Chemistry', 'Hydroxy Compounds and Ethers',
            'Carbonyl Compounds', 'Carboxylic Acids', 'Organic Nitrogen Compounds', 'Biomolecules'
        ],
        'Mathematics': [
            'Applications of Matrices and Determinants', 'Complex Numbers',
            'Theory of Equations', 'Inverse Trigonometric Functions',
            'Two Dimensional Analytical Geometry-II', 'Applications of Vector Algebra',
            'Differential Calculus - Applications', 'Differentials and Partial Derivatives',
            'Applications of Integration', 'Ordinary Differential Equations',
            'Probability Distributions', 'Discrete Mathematics'
        ],
        'Biology': [
            'Reproduction in Organisms', 'Sexual Reproduction in Flowering Plants',
            'Human Reproduction', 'Principles of Inheritance and Variation',
            'Molecular Basis of Inheritance', 'Evolution', 'Human Health and Disease',
            'Biotechnology Principles and Processes', 'Organisms and Populations', 'Ecosystem'
        ],
        'Computer Science': [
            'Function', 'Data Abstraction', 'Scoping', 'Algorithmic Strategies',
            'Python - Variables and Operators', 'Control Structures', 'Python Functions',
            'Strings and String Manipulations', 'Lists Tuples Sets and Dictionary',
            'Python Classes and Objects', 'Database Concepts', 'Structured Query Language (SQL)',
            'Python and CSV Files', 'Importing C++ Programs in Python', 'Data Visualization using Pyplot'
        ],
        'Commerce': [
            'Principles of Management', 'Management by Objectives (MBO)',
            'Financial Markets', 'Capital Market', 'Money Market', 'Stock Exchange',
            'Securities and Exchange Board of India (SEBI)', 'Human Resource Management',
            'Consumer Protection'
        ],
        'Accountancy': [
            'Accounts from Incomplete Records', 'Accounts of Not-for-Profit Organisation',
            'Partnership Basic Concepts', 'Admission of a Partner', 'Retirement of a Partner',
            'Company Accounts', 'Financial Statement Analysis', 'Ratio Analysis'
        ],
        'Economics': [
            'Introduction to Macro Economics', 'National Income',
            'Theories of Employment and Income', 'Money and Banking',
            'Fiscal Economics', 'International Economics', 'Environmental Economics'
        ],
        'English': [
            'Two Gentlemen of Verona', 'In Celebration of Being Alive',
            'The Summit', 'The Chair', 'On the Rule of the Road'
        ],
        'Tamil': [
            'உயிரினும் சிறந்தன்று', 'பிறகொரு நாள் கோடை', 'கம்பராமாயணம்',
            'சிலப்பதிகாரம்', 'புறநானூறு', 'தேவாரம்'
        ]
    }
}


def get_supported_classes():
    """Return all supported Tamil Nadu State Board classes (Classes 6-12)."""
    return list(TN_CLASSES)


def get_supported_subjects(class_grade):
    """Return verified subjects for a specific class."""
    if class_grade not in TN_CURRICULUM_DATA:
        return []
    return list(TN_CURRICULUM_DATA[class_grade].keys())


def get_supported_chapters(class_grade, subject):
    """Return verified chapters for a specific class and subject."""
    class_data = TN_CURRICULUM_DATA.get(class_grade, {})
    return class_data.get(subject, [])


def seed_curriculum_metadata(db):
    """Seed curriculum table in database if empty."""
    existing_count = db.query(Curriculum).filter_by(board='Tamil Nadu State Board').count()
    if existing_count > 0:
        return existing_count

    count = 0
    for class_name, subjects in TN_CURRICULUM_DATA.items():
        for subject_name, chapters in subjects.items():
            for idx, chapter in enumerate(chapters, start=1):
                cur = Curriculum(
                    board='Tamil Nadu State Board',
                    class_grade=class_name,
                    subject=subject_name,
                    chapter_number=idx,
                    chapter_name=chapter,
                    description=f"Tamil Nadu Samacheer Kalvi {class_name} {subject_name} Chapter {idx}: {chapter}"
                )
                db.add(cur)
                count += 1
    
    db.commit()
    print(f"Seeded {count} Tamil Nadu State Board curriculum chapters.")
    return count
