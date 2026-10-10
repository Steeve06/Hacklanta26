# ruff: noqa: E501
"""The built-in flashcard library: short, general study and awareness cards, not tied to any course.

Each entry is (slug, topic, front, back). Slugs are stable ids, so editing a card's text updates it
in place and removing an entry retires the card. `services.cards.sync_cards` loads this list.
"""

CARDS: list[tuple[str, str, str, str]] = [
    # Study skills
    ("retrieval-practice", "study_skills",
     "What is retrieval practice?",
     "Pulling information out of memory, for example with flashcards or practice questions. It "
     "builds longer-lasting memory than rereading the same material."),
    ("spaced-practice", "study_skills",
     "Why spread study over several days instead of cramming?",
     "Spacing sessions out (the spacing effect) leads to better long-term retention than the same "
     "time spent in one block."),
    ("interleaving", "study_skills",
     "What does interleaving mean when you practise?",
     "Mixing different kinds of problems in one session, so you have to choose the right method "
     "each time instead of repeating one."),
    ("feynman-technique", "study_skills",
     "What is the Feynman technique?",
     "Explain an idea in plain words as if teaching a beginner. The places where you get stuck show "
     "what you don't understand yet."),
    ("pomodoro", "study_skills",
     "What is the Pomodoro technique?",
     "Work in focused blocks (classically 25 minutes) separated by short breaks, with a longer "
     "break after about four blocks."),
    ("highlighting", "study_skills",
     "Is highlighting an effective way to study on its own?",
     "Not really. Research rates it low: it feels productive but does little for memory unless you "
     "follow it with testing yourself."),
    ("two-minute-rule", "study_skills",
     "What is the two-minute rule for getting started?",
     "When you're stuck procrastinating, commit to just two minutes of the task. Starting is usually "
     "the hardest part."),
    # Memory
    ("forgetting-curve", "memory",
     "What does Ebbinghaus's forgetting curve show?",
     "Memory of new information drops fastest in the first hours and days, unless you review it. "
     "Each review flattens the curve."),
    ("testing-effect", "memory",
     "What is the testing effect?",
     "Taking a test on material improves later memory of it more than spending the same time "
     "studying it again."),
    ("chunking", "memory",
     "What is chunking?",
     "Grouping items into meaningful units (like a phone number in three parts) so working memory "
     "can hold more."),
    ("sleep-memory", "memory",
     "How does sleep help you learn?",
     "Sleep consolidates memories formed during the day. Pulling an all-nighter before an exam "
     "usually hurts recall."),
    ("dual-coding", "memory",
     "What is dual coding?",
     "Combining words with visuals, like a diagram or timeline, so you have two routes back to the "
     "same idea."),
    ("generation-effect", "memory",
     "What is the generation effect?",
     "You remember information better when you produce it yourself (fill in the blank, predict the "
     "answer) than when you just read it."),
    ("method-of-loci", "memory",
     "What is the method of loci, or memory palace?",
     "A memory trick where you place things to remember along a route through a familiar place, "
     "then walk the route in your mind to recall them."),
    # Focus
    ("multitasking", "focus",
     "Can people really multitask on two thinking tasks?",
     "Mostly no. The brain switches between tasks, and each switch costs time and accuracy."),
    ("phone-nearby", "focus",
     "Does it matter if your phone is on the desk while you study, even face down?",
     "Studies suggest it can. A visible phone pulls on attention, so putting it in another room is "
     "an easy win."),
    ("attention-residue", "focus",
     "What is attention residue?",
     "When you switch tasks, part of your attention stays on the previous one for a while, which "
     "lowers performance on the new one."),
    ("deep-work", "focus",
     "What makes a good deep-work session?",
     "A clear goal, a fixed time block, no notifications, and everything you need within reach "
     "before you start."),
    ("implementation-intention", "focus",
     "What is an implementation intention?",
     "A plan in the form \"When X happens, I will do Y\", for example \"After lunch I'll review my "
     "notes for 20 minutes\". It makes follow-through more likely."),
    ("habit-stacking", "focus",
     "What is habit stacking?",
     "Attaching a new habit to one you already have, like a flashcard deck right after your "
     "morning coffee."),
    ("parkinsons-law", "focus",
     "What is Parkinson's law?",
     "Work expands to fill the time available for it. Shorter, set time boxes help you finish."),
    # Well-being
    ("sleep-hours", "wellbeing",
     "How much sleep do young adults generally need?",
     "Health guidelines recommend about 7 to 9 hours a night for adults, including college "
     "students."),
    ("exercise-brain", "wellbeing",
     "How can a short walk help your studying?",
     "Even brief physical activity can improve mood and attention for a while afterwards. A walk "
     "between sessions is a good break."),
    ("box-breathing", "wellbeing",
     "What is box breathing?",
     "Breathe in for 4 counts, hold for 4, breathe out for 4, hold for 4, and repeat. A simple way "
     "to calm down before an exam."),
    ("hydration", "wellbeing",
     "Can mild dehydration affect concentration?",
     "Yes. Even mild dehydration is linked to worse mood and attention, so keep water nearby."),
    ("breaks-screen", "wellbeing",
     "What is the 20-20-20 rule for screen time?",
     "Every 20 minutes, look at something about 20 feet (6 m) away for 20 seconds to ease eye "
     "strain."),
    ("asking-for-help", "wellbeing",
     "When is a good time to go to office hours or tutoring?",
     "Early, before you're far behind. Asking for help is a normal study strategy, not a sign of "
     "failing."),
    ("growth-mindset", "wellbeing",
     "What is a growth mindset?",
     "The belief that abilities can improve with effort and good strategies, rather than being "
     "fixed."),
    # Money
    ("compound-interest", "money",
     "What is compound interest?",
     "Interest earned on both your original money and the interest it already earned, so savings "
     "(or debt) grow faster over time."),
    ("rule-of-72", "money",
     "What is the rule of 72?",
     "Divide 72 by an annual interest rate to estimate how many years it takes money to double. "
     "At 6%, about 12 years."),
    ("emergency-fund", "money",
     "What is an emergency fund?",
     "Savings set aside for unexpected costs like a car repair, so you don't have to rely on a "
     "credit card."),
    ("credit-utilization", "money",
     "What is credit utilization?",
     "How much of your available credit you're using. Keeping it low helps your credit score."),
    ("apr", "money",
     "What does APR stand for?",
     "Annual percentage rate: the yearly cost of borrowing, including interest and some fees."),
    ("budget-50-30-20", "money",
     "What is the 50/30/20 budget rule?",
     "A rough guide: about 50% of income for needs, 30% for wants and 20% for savings or paying "
     "down debt."),
    ("subsidized-loans", "money",
     "What is the difference between subsidized and unsubsidized federal student loans?",
     "For subsidized loans the government pays the interest while you're in school at least half "
     "time. Unsubsidized loans build up interest from the start."),
    # Digital life
    ("phishing", "digital",
     "What is phishing?",
     "A message that pretends to be from someone you trust to trick you into giving away a password "
     "or clicking a harmful link."),
    ("two-factor", "digital",
     "Why turn on two-factor authentication?",
     "It adds a second check, like a code from an app, so a stolen password alone isn't enough to "
     "get into your account."),
    ("password-manager", "digital",
     "Why use a password manager?",
     "It lets you use a different long password for every site without memorising them, so one leak "
     "doesn't expose everything."),
    ("public-wifi", "digital",
     "What should you be careful about on public Wi-Fi?",
     "Other people on the network may be able to snoop. Stick to HTTPS sites and avoid sensitive "
     "logins if you can."),
    ("lateral-reading", "digital",
     "What is lateral reading?",
     "Checking a source by opening other tabs to see what independent sites say about it, instead "
     "of only reading the source itself."),
    ("software-updates", "digital",
     "Why install software updates promptly?",
     "Many updates fix security holes that attackers already know about."),
    ("backups-321", "digital",
     "What is the 3-2-1 backup rule?",
     "Keep 3 copies of important files, on 2 different kinds of storage, with 1 copy off-site or in "
     "the cloud."),
    # Science
    ("photosynthesis", "science",
     "What does photosynthesis produce?",
     "Plants use light, water and carbon dioxide to make glucose (sugar) and release oxygen."),
    ("dna", "science",
     "What does DNA stand for?",
     "Deoxyribonucleic acid, the molecule that carries genetic instructions in living things."),
    ("speed-of-light", "science",
     "Roughly how fast does light travel?",
     "About 300,000 km per second in a vacuum, fast enough to reach the Moon in just over a "
     "second."),
    ("correlation-causation", "science",
     "Does correlation prove causation?",
     "No. Two things can move together because of chance or a third factor, so a link alone doesn't "
     "show one causes the other."),
    ("placebo", "science",
     "What is the placebo effect?",
     "A real improvement people feel after a treatment with no active ingredient, because they "
     "expect it to work."),
    ("antibiotics-viruses", "science",
     "Do antibiotics work against viruses like the cold or flu?",
     "No. Antibiotics treat bacterial infections. Overusing them helps bacteria become resistant."),
    ("water-boiling", "science",
     "At what temperature does water boil at sea level?",
     "100 °C, or 212 °F. At higher altitudes it boils at a lower temperature."),
    # World
    ("continents", "world",
     "How many continents are there in the most common model taught in the US?",
     "Seven: Africa, Antarctica, Asia, Australia (Oceania), Europe, North America and South "
     "America."),
    ("largest-ocean", "world",
     "Which is the largest ocean?",
     "The Pacific. It covers more area than all the land on Earth combined."),
    ("un-members", "world",
     "About how many member states does the United Nations have?",
     "193."),
    ("three-branches", "world",
     "What are the three branches of the US federal government?",
     "Legislative (Congress), executive (the President) and judicial (the courts)."),
    ("bill-of-rights", "world",
     "What is the Bill of Rights?",
     "The first ten amendments to the US Constitution, which protect rights like free speech and a "
     "fair trial."),
    ("greenhouse-effect", "world",
     "What is the greenhouse effect?",
     "Gases such as carbon dioxide trap heat in the atmosphere. More of them warms the planet."),
    ("world-population", "world",
     "Roughly how many people live on Earth?",
     "About 8 billion, a mark passed in 2022."),
]  # fmt: skip
