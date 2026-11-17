# Off Script: New Features Report

Project: Off Script: The Last Light of Aether (CSE339 Capstone, SIH26195)

Team: Devansh Patel, Devesh Singh, Anurag Patel, Siddhank Kashyap, Himanshu Srivastava, Aniket Mondal

Date: 18 November 2026

## 1. Our project in short

- Off Script is a 2D adventure game where the characters are controlled by AI.
- Three friends, Aria, Kabir and Meera, must carry the Sun Crystal to the Lighthouse before a storm.
- Each character has its own goal, its own knowledge and its own plan. When something goes wrong, it changes the plan by itself.
- A rules engine checks every action, so no character can break the game rules.
- There are two modes: **Watch** (the AI team plays alone) and **Game** (you play one character, and the other two think for themselves).

Since the last review we added **three new things**: Mind View, the Team Journal and Gameplay Graphs.

## 2. New feature 1: Mind View (see inside a character's head)

**What it is:** a panel that shows what a character is thinking.

**Where to see it:** during a game, open the **Team** tab and click **"Look inside Meera's head"**.

**What it shows:**

- **Why this plan?** All the options the character had, the one it chose, and **who chose it**: its rules, the AI, a lesson from a past game, or the player's radio order. It also shows the reason.
- **Believes vs reality:** what the character thinks next to what is really true. Example: Meera thinks the bridge is broken, but Kabir already fixed it while she was in the forest.
- **Memories:** what it saw or was told, newest first.
- **On the map:** purple bubbles and "ghosts" show where the character's knowledge is out of date.

**Why it matters:** it proves our characters act only on what they know, not on the hidden game data, just like real people.

## 3. New feature 2: Team Journal (characters learn across games)

**What it is:** characters remember lessons from earlier games and get better.

**How it works:**

- After every Watch game, each character looks back: "Where did I wait a long time when I could have done something else?"
- It writes that down as a lesson. Example (Aria): "Last time I waited 110s at the Temple Entrance. Next time: puzzle out the symbols myself."
- The next Watch game tests the lesson.
- If the team finishes faster or with a better ending, the lesson is **kept**. If not, it is **dropped**.

**Real result from our game:**

- Game 1: 330 seconds. Aria writes a lesson.
- Game 2: 325 seconds. 5 seconds faster, so the lesson is **kept**.
- Game 3: a new lesson made it 360 seconds (35 seconds slower), so it was **dropped**.

**Where to see it:**

- Main menu, scroll down: **"Team journal: learning across games"** (learning curve and all lessons).
- Ending screen: **"What the team learned"**.
- In the second game, a pop-up appears: **"Aria remembers an earlier game…"**

**Why the test is fair:** a Watch game plays exactly the same every time with the same lessons, and we test only one lesson at a time. So any change in the result comes from the lesson.

## 4. New feature 3: Gameplay Graphs

**What it is:** graphs that show how a game was played, as our mentor asked.

**Where to see it:**

- During a game: the new **Graphs** tab (updates live).
- On the ending screen: the **"Gameplay graphs"** section.
- From the main menu: the **"Gameplay graphs"** button (a full page).

**Graphs for one game:**

- **Who did what, and when:** one row per character. Blue means travelling, orange means working on a task, grey means waiting. Story milestones are marked with dashed lines.
- **Mission progress over time:** how many story steps were reached as time went on. In Game mode, a red line shows the storm deadline.
- **How each character spent its time:** % travelling, working and waiting. Example: Aria waits about 35% of the time, which is exactly what the Team Journal learns to fix.
- **Decisions made by each character:** plan changes, adaptations, AI choices, lessons used and failed actions.

**Graphs for all games (main menu page):**

- Summary: finished games, % where the beacon was lit, fastest beacon, average game length.
- Game length per game (Watch and Game mode shown differently).
- How often each ending happened.
- A table of all games.

## 5. Why our features are unique

- Most games **hide** how the AI decides. We **show** it: the options, who chose, the reason, and what the character believes.
- In most games, characters **forget** everything when the game restarts. Ours **remember** and improve.
- Our characters **test** what they learn. Bad ideas are dropped automatically.
- It is **safe**: a lesson or an AI choice can only pick a move the rules already allow, so it can never cheat.
- The graphs turn the gameplay into **measurable data**, so we can prove the learning works (330s, then 325s).
- It is based on research papers: ReAct, LLM-Modulo, Generative Agents and Reflexion.

## 6. Who did what (individual work)

### Devansh Patel (Backend and API)

- Sent each character's "mind" to the screen as part of the game state.
- Built the journal API: GET /api/journal and POST /api/journal/reset.
- Connected the journal to the server, so every finished game is recorded exactly once.
- Built the graphs API: GET /api/runs/{id}/analytics.

### Devesh Singh (Database and simulation loop)

- Created new database tables for lessons and finished games (the learning curve).
- Saved the decision trace and the waiting log with each game.
- Checked that Watch games repeat exactly, which makes the lesson test fair.
- Built the graph data from the game's recorded events: travel times, work times and waiting times.

### Anurag Patel (Story, adaptation logic and endings)

- Wrote the rules to find a lesson: a wait of 30 seconds or more, when another option was possible.
- Defined the ranking of endings and the keep/drop decision for lessons.
- Defined the story milestones used in the "Mission progress" graph.

### Siddhank Kashyap (Memory, knowledge, research and testing)

- Built the "believes vs reality" comparison and the memory list, without revealing hidden things.
- Fixed a bug: a character still believed it carried an item after using it.
- Wrote the new tests: 21 backend and 7 frontend.
- Checked all features live in the browser, and linked the features to the research papers.

### Himanshu Srivastava (LLM and character agents)

- Recorded every decision inside the agent: the options, who chose, and the AI's one-line reason.
- Recorded every waiting time, with the other options the character had.
- Made the planner use a lesson only in the right situation, and only if the move is still valid.
- Provided the decision counts for the "Decisions made by each character" graph.

### Aniket Mondal (2D map and user interface)

- Built the Mind View panel, the "Look inside" buttons, and the purple bubbles and ghosts on the map.
- Built the Team Journal card with the learning curve, and the "What the team learned" box.
- Built all the gameplay graphs: the Graphs tab, the ending-screen graphs and the Gameplay graphs page.

## 7. Testing

- Backend: **222 tests pass** (21 new).
- Frontend: **37 tests pass** (7 new).
- Checked live in the browser: Mind View, two Watch games with a lesson kept, and all the graphs. There were no errors.

## 8. Demo plan for tomorrow (about 5 minutes)

1. Main menu: press "Forget everything" so the journal starts empty.
2. Press **Watch the AI play**. At about 1:40, pause. Open **Team**, then **Look inside Meera's head**, and show "thinks broken, really open" and the purple map.
3. Open the **Graphs** tab and show the live timeline and progress graph.
4. Skip to the end. Show **"What the team learned"** and the gameplay graphs on the ending screen.
5. Press **Play again**. Show the pop-up "Aria remembers an earlier game", then Aria's Mind View: "Lesson from a past game".
6. At the end: "5 seconds faster, lesson kept". Back on the main menu, show the **Team Journal** and the **Gameplay graphs** page.

## 9. Questions sir may ask

**Q. Is this real AI or just rules?**
The base is rules on purpose, because research (the LLM-Modulo paper) shows AI alone makes planning mistakes. The AI chooses between valid strategies with a reason, talks in character, and writes the story. The Mind View shows exactly when the AI chose.

**Q. Generative Agents already did memory and reflection. What is new?**
They never tested whether a lesson really helped, their characters sometimes broke rules, and it cost thousands of dollars. Ours tests every lesson, can never break a rule, and runs on free AI or with no AI at all.

**Q. Only 5 seconds faster?**
Our starting plan was already good. The important part is the method: try, measure, keep or drop. It also correctly dropped a lesson that made things 35 seconds worse.

**Q. Did you train a machine learning model?**
No. It is learning from experience in words (like the Reflexion paper). Every lesson can be read by a person.

**Q. Where do the graph numbers come from?**
From the events the game records: when each character started and finished travelling or working, and when each story step was reached. Nothing is made up.
