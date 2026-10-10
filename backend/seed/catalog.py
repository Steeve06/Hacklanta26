"""Static definitions for the demo term: courses, assessments and instructor quiz questions.

Week numbers are 1-based weeks of the term. `day` is 0 = Monday … 6 = Sunday of that week.
"""

CHAPTER_WEEKS = [1, 3, 4, 6, 8, 10, 11, 13]

COURSES = [
    {
        "code": "CS 201",
        "slug": "cs201",
        "title": "Data Structures",
        "color": "#3a63b8",
        "instructor": ("prof.okafor@pulse.test", "Ada", "Okafor"),
        "office_hours": "Tuesdays and Thursdays 14:00–15:30, Hartley Hall 312, or by appointment",
        "description": (
            "How to organize data so programs stay fast as inputs grow. We study arrays, linked "
            "lists, stacks, queues, hash tables, trees, heaps and graphs, analyze their costs with "
            "Big-O notation, and practise choosing the right structure for a problem."
        ),
        "grading": [
            ("Homework", 40),
            ("Quizzes", 15),
            ("Discussions", 10),
            ("Midterm exam", 15),
            ("Final project", 20),
        ],
        "assessments": [
            ("homework", "Problem Set 1: Growth rates", [1], 2, 4, 6, 120),
            ("quiz", "Quiz 1: Arrays and lists", [2, 3], 4, 3, 5, None),
            ("discussion", "When would you pick a linked list?", [3], 5, 2, 3, None),
            ("homework", "Problem Set 2: Stacks and queues", [4], 6, 4, 8, 150),
            ("quiz", "Quiz 2: Hashing", [5], 7, 3, 5, None),
            ("discussion", "Hash collisions in the wild", [5], 8, 2, 3, None),
            ("homework", "Problem Set 3: Binary search trees", [6], 9, 4, 8, 180),
            ("quiz", "Quiz 3: Heaps", [7], 11, 3, 5, None),
            ("discussion", "Modelling your commute as a graph", [8], 13, 2, 4, None),
            ("homework", "Final project: Route planner", [7, 8], 15, 2, 20, 420),
        ],
    },
    {
        "code": "PSY 101",
        "slug": "psy101",
        "title": "Introduction to Psychology",
        "color": "#b4572e",
        "instructor": ("dr.marsh@pulse.test", "Lena", "Marsh"),
        "office_hours": "Mondays 10:00–12:00, Behavioral Sciences 118, or on video by appointment",
        "description": (
            "A survey of psychology as a science: how psychologists study behavior, the brain, "
            "perception, learning, memory, motivation and social influence, with attention to how "
            "each finding was established and where it applies to everyday life."
        ),
        "grading": [
            ("Response papers", 30),
            ("Quizzes", 20),
            ("Discussions", 15),
            ("Midterm exam", 15),
            ("Final exam", 20),
        ],
        "assessments": [
            ("discussion", "A belief about behavior you'd like tested", [1], 2, 1, 3, None),
            ("homework", "Response paper 1: Reading a study", [2], 3, 4, 7, 120),
            ("quiz", "Quiz 1: Methods and the brain", [2, 3], 4, 4, 5, None),
            ("homework", "Response paper 2: Perception in design", [4], 6, 4, 7, 120),
            ("discussion", "Reinforcement schedules you live with", [5], 8, 2, 4, None),
            ("quiz", "Quiz 2: Learning", [5], 8, 4, 5, None),
            ("homework", "Response paper 3: A study plan from memory research", [6], 10, 4, 8, 150),
            ("quiz", "Quiz 3: Memory and motivation", [6, 7], 11, 4, 5, None),
            ("discussion", "The bystander effect, then and now", [8], 13, 2, 4, None),
            ("homework", "Response paper 4: Social influence", [8], 14, 4, 8, 150),
        ],
    },
    {
        "code": "BUS 210",
        "slug": "bus210",
        "title": "Business Communication",
        "color": "#2e7d5b",
        "instructor": ("prof.reyes@pulse.test", "Daniel", "Reyes"),
        "office_hours": "Wednesdays 13:00–15:00, Commerce Building 204",
        "description": (
            "Writing and speaking for the workplace: planning messages for real readers, "
            "email and digital etiquette, delivering bad news, persuasion, reports, presentations "
            "and communicating in teams and across cultures."
        ),
        "grading": [
            ("Writing assignments", 45),
            ("Quizzes", 10),
            ("Discussions", 15),
            ("Presentation", 15),
            ("Participation", 15),
        ],
        "assessments": [
            ("discussion", "The worst email you ever received", [1], 2, 3, 3, None),
            ("homework", "Rewrite: plain-language memo", [2], 3, 3, 8, 90),
            ("quiz", "Quiz 1: Planning and email", [2, 3], 4, 2, 3, None),
            ("homework", "Bad-news letter", [4], 6, 3, 10, 120),
            ("discussion", "Persuasion you fell for", [5], 7, 3, 3, None),
            ("quiz", "Quiz 2: Bad news and persuasion", [4, 5], 8, 2, 3, None),
            ("homework", "Short analytical report", [6], 10, 3, 12, 240),
            ("discussion", "Slides that worked (and didn't)", [7], 11, 3, 3, None),
            ("quiz", "Quiz 3: Reports and presentations", [6, 7], 12, 2, 4, None),
            ("homework", "Recorded presentation", [7, 8], 14, 3, 15, 300),
        ],
    },
]

QUIZ_QUESTIONS = {
    ("CS 201", 1): [
        (
            "Reading the element at a given index of an array takes…",
            ["O(1)", "O(log n)", "O(n)", "O(n²)"],
            0,
        ),
        (
            "Appending to a dynamic array that doubles its capacity is amortized O(1).",
            ["True", "False"],
            0,
        ),
        (
            "Which operation is O(1) on a singly linked list?",
            [
                "Insert at the head",
                "Access the 10th element",
                "Delete the tail",
                "Search for a value",
            ],
            0,
        ),
        (
            "Growing an array by a fixed 10 slots each time keeps appends amortized O(1).",
            ["True", "False"],
            1,
        ),
    ],
    ("CS 201", 2): [
        (
            "What decides which bucket a key goes into?",
            [
                "Its hash modulo the table size",
                "Its insertion order",
                "Its length",
                "Alphabetical order",
            ],
            0,
        ),
        (
            "Separate chaining handles collisions by…",
            [
                "Storing a list in each bucket",
                "Probing the next slot",
                "Rejecting the insert",
                "Sorting the keys",
            ],
            0,
        ),
        ("A hash table can efficiently return all keys between A and F.", ["True", "False"], 1),
        (
            "When the load factor passes its threshold, the table…",
            [
                "Resizes and rehashes",
                "Deletes old keys",
                "Switches to a list",
                "Stops accepting inserts",
            ],
            0,
        ),
    ],
    ("CS 201", 3): [
        (
            "In a min-heap, the smallest key is always at…",
            ["The root", "The last leaf", "The leftmost leaf", "Any position"],
            0,
        ),
        ("A binary heap is a sorted array.", ["True", "False"], 1),
        (
            "Where are the children of the node at index i?",
            ["2i + 1 and 2i + 2", "i + 1 and i + 2", "i/2 and i/2 + 1", "2i and 3i"],
            0,
        ),
        (
            "Building a heap from n items with heapify takes…",
            ["O(n)", "O(n log n)", "O(log n)", "O(n²)"],
            0,
        ),
    ],
    ("PSY 101", 1): [
        (
            "Which method can establish cause and effect?",
            ["Experiment", "Survey", "Case study", "Correlational study"],
            0,
        ),
        ("Random assignment determines who is invited into a study.", ["True", "False"], 1),
        (
            "The fatty layer that speeds signals along an axon is the…",
            ["Myelin sheath", "Dendrite", "Synapse", "Cell body"],
            0,
        ),
        (
            "Which structure is critical for forming new long-term memories?",
            ["Hippocampus", "Cerebellum", "Medulla", "Occipital lobe"],
            0,
        ),
    ],
    ("PSY 101", 2): [
        (
            "In Pavlov's work, the tone after conditioning is the…",
            [
                "Conditioned stimulus",
                "Unconditioned stimulus",
                "Unconditioned response",
                "Neutral response",
            ],
            0,
        ),
        (
            "Negative reinforcement removes something unpleasant to increase a behavior.",
            ["True", "False"],
            0,
        ),
        (
            "Which schedule produces behavior most resistant to extinction?",
            ["Variable-ratio", "Continuous", "Fixed-interval", "Fixed-ratio"],
            0,
        ),
        (
            "Bandura's Bobo doll studies demonstrated…",
            ["Observational learning", "Classical conditioning", "Shaping", "Extinction"],
            0,
        ),
    ],
    ("PSY 101", 3): [
        (
            "Grouping digits of a phone number into three parts is called…",
            ["Chunking", "Priming", "Rehearsal", "Interference"],
            0,
        ),
        ("Spacing study sessions out improves long-term retention.", ["True", "False"], 0),
        (
            "Paying for something people already enjoy can reduce their interest. This is the…",
            ["Overjustification effect", "Bystander effect", "Testing effect", "Placebo effect"],
            0,
        ),
        (
            "The two-factor theory says emotion requires arousal and…",
            ["A cognitive label", "A facial expression", "A reflex", "A reward"],
            0,
        ),
    ],
    ("BUS 210", 1): [
        (
            "For a routine request, where should the main point go?",
            ["First", "In the middle", "At the end", "In the subject line only"],
            0,
        ),
        ("Active voice names who performs the action.", ["True", "False"], 0),
        (
            "Which is the strongest subject line?",
            ["Approve venue deposit by Thursday?", "Question", "Update", "Following up"],
            0,
        ),
        (
            'Jargon and vague terms like "soon" are examples of…',
            ["Semantic noise", "Physical noise", "Feedback", "Channel richness"],
            0,
        ),
    ],
    ("BUS 210", 2): [
        (
            "In the indirect bad-news plan, what comes right after the buffer?",
            ["Reasons", "The bad news", "The goodwill close", "An apology"],
            0,
        ),
        ("A good buffer hints that the answer will be yes.", ["True", "False"], 1),
        ("Persuasion through credibility is called…", ["Ethos", "Pathos", "Logos", "Kairos"], 0),
        (
            "In AIDA, the final step asks the reader to…",
            ["Act", "Pay attention", "Feel interest", "Read the appendix"],
            0,
        ),
    ],
    ("BUS 210", 3): [
        (
            "Which section of a report should stand on its own for busy readers?",
            ["Executive summary", "Appendix", "References", "Table of contents"],
            0,
        ),
        (
            "Starting a bar chart's axis above zero can exaggerate differences.",
            ["True", "False"],
            0,
        ),
        (
            "A good presentation slide usually holds…",
            ["One idea", "Every detail of the talk", "Full paragraphs", "As many bullets as fit"],
            0,
        ),
        (
            "Cultures where meaning relies heavily on context and relationships are called…",
            ["High-context", "Low-context", "Individualist", "Monochronic"],
            0,
        ),
    ],
}

POLICIES = {
    "late_work": (
        "Work submitted after the due date but before the late cut-off loses 10% per day. "
        "Nothing is accepted after the cut-off unless you have an extension. Ask for extensions "
        "before the due date whenever you can."
    ),
    "academic_integrity": (
        "Discuss ideas freely, but write and code your own submissions. Cite every source you "
        "use, including AI tools. Suspected violations go to the Office of Student Conduct."
    ),
}

WEEK_TOPICS = {
    7: "Review and midterm",
    14: "Review",
    15: "Finals week",
}

STUDENTS = [
    {"email": "maya@pulse.test", "first": "Maya", "last": "Chen", "profile": "on_track"},
    {"email": "sam@pulse.test", "first": "Sam", "last": "Patel", "profile": "slightly_behind"},
    {"email": "jordan@pulse.test", "first": "Jordan", "last": "Brooks", "profile": "badly_behind"},
    {"email": "alex@pulse.test", "first": "Alex", "last": "Rivera", "profile": "extension"},
    {"email": "riley@pulse.test", "first": "Riley", "last": "Okoye", "profile": "new"},
]

CLASSMATES = [
    ("Priya", "Nair"),
    ("Tomás", "García"),
    ("Hannah", "Weiss"),
    ("Kwame", "Mensah"),
]

CLASSMATE_POSTS = [
    "I'd start from what the reader needs to do next. In my internship the messages that got "
    "answered fastest were the ones with the request in the first line.",
    "I went back to the chapter for this one. The part that stuck with me is that the trade-off "
    "only shows up at scale, so a small test can hide the problem completely.",
    "Counterpoint: sometimes the 'slow' option is fine because the data never gets big. I think "
    "the real skill is knowing your input sizes before picking anything.",
    "This happened at my part-time job last month, and honestly the example in the reading "
    "described it almost exactly. Curious whether anyone saw the opposite.",
]
