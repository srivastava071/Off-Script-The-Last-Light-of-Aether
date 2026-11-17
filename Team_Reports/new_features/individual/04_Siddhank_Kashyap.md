# Report: Siddhank Kashyap

Role: Memory, knowledge, research, documentation and testing

Project: Off Script: The Last Light of Aether (CSE339 Capstone)

Topic: two new features (Mind View and Team Journal)

Date: 18 November 2026

## The two new features (short)

- **Feature 1: Mind View.** You can look inside a character's head. It shows the options the character had, which one it picked, and who picked it (its rules, the AI, a lesson from a past game, or the player's order). It also shows what the character believes next to what is really true, and its recent memories. On the map, purple bubbles and "ghosts" show where its knowledge is out of date.
- **Feature 2: Team Journal (learning across games).** After every Watch run, a character finds a place where it waited a long time when it could have done something else, and writes a lesson. The next Watch run tests the lesson. If the team finishes sooner or with a better ending, the lesson is kept. If not, it is dropped.

Real result: Run 1 took 330s. Aria learned "decode the symbols myself", and Run 2 took 325s, so the lesson was kept. Her next lesson made Run 3 take 360s, so it was dropped.

## My work

My part was the "believes vs reality" part of the Mind View, the memory list, fixing a knowledge bug, and testing both features.

### 1. Believes vs reality

- For each character I compare what it **believes** with what is **really true**, for: every road, every item, the temple lock, the lighthouse, the flood, and where the teammates are.
- For each fact the screen shows: what it thinks, what is true, and how long ago it learned it.
- Example: Meera thinks the Main Bridge is broken, but Kabir already fixed it while she was in the forest.
- **Safety:** I only compare things the player can already see on the map. Hidden routes and undiscovered traps are never revealed.

### 2. Memory list

- The Mind View shows the character's last 8 important memories, newest first.
- Each memory says where it came from: "saw", "did", "told by Kabir", or "Meera's signal".
- Small routine memories like "waits for 10s" are hidden, so the list stays useful.

### 3. Bug I found and fixed

- After Kabir used the timber to repair the bridge, he still believed he was carrying it.
- Now, when an item leaves a character's hands (used up or given away), the character updates its belief.

### 4. Testing

- I wrote **16 new backend tests**: 8 for Mind View and 8 for the Team Journal.
- I wrote **5 new frontend tests** for the Mind View panel, the "Look inside" button and the lesson labels.
- I checked both features live in the browser: two Watch runs, the lesson pop-up, and the journal. There were no errors.
- Result: 217 backend tests and 35 frontend tests pass.

### 5. Research link

- The Mind View follows the ReAct paper (show the reasoning) and LLM-Modulo (options, then a choice, then a check).
- The Team Journal follows Generative Agents (reflection) and Reflexion (learning from mistakes in words).

## How to show it

- In a Watch run, pause at about 1:40, open the Team tab and click "Look inside Meera's head". Point to "Main Bridge: thinks broken, really open".

## Files I worked on

- backend/app/schemas/views.py (believes-vs-reality comparison and memory list)
- backend/app/engine/knowledge.py (bug fix for used items)
- backend/tests/test_mind_view.py and backend/tests/test_learning.py (new tests)
- frontend/src/components/mind.test.tsx (new frontend tests)
