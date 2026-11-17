# Report: Aniket Mondal

Role: 2D map, user interface and player controls

Project: Off Script: The Last Light of Aether (CSE339 Capstone)

Topic: two new features (Mind View and Team Journal)

Date: 18 November 2026

## The two new features (short)

- **Feature 1: Mind View.** You can look inside a character's head. It shows the options the character had, which one it picked, and who picked it (its rules, the AI, a lesson from a past game, or the player's order). It also shows what the character believes next to what is really true, and its recent memories. On the map, purple bubbles and "ghosts" show where its knowledge is out of date.
- **Feature 2: Team Journal (learning across games).** After every Watch run, a character finds a place where it waited a long time when it could have done something else, and writes a lesson. The next Watch run tests the lesson. If the team finishes sooner or with a better ending, the lesson is kept. If not, it is dropped.

Real result: Run 1 took 330s. Aria learned "decode the symbols myself", and Run 2 took 325s, so the lesson was kept. Her next lesson made Run 3 take 360s, so it was dropped.

## My work

My part was everything the player sees for the two new features.

### 1. Mind View panel

- In the Team tab, each character card now has a button: **"Look inside Aria's head"**, with a counter like "3 out of date".
- The panel has four parts:
  - **Why this plan?** A badge shows who chose it (rules, AI, lesson or your order). Below it are the reason and the list of options, with the chosen one highlighted.
  - **Believes vs reality:** out-of-date facts in yellow, "Thinks: broken · Really: open". A "Show everything" button shows all facts.
  - **Lessons from past games**, if the character has any.
  - **Recent memories**, with an icon for where each came from.
- Small faces at the top switch between characters.

### 2. Purple map layer

- While a Mind View is open, the map shows that character's picture of the island:
  - a thought bubble on each road it is wrong about, for example "Meera thinks: broken";
  - purple **ghosts** where it wrongly thinks a teammate or an item is, for example "Kabir?" at the harbour;
  - a title at the top: "Meera's picture of the island · 2 out of date".
- Clicking a character on the map switches the Mind View to that character.

### 3. Team Journal screens

- **Main menu:** a new Team Journal card with a short explanation, a **learning curve** chart (seconds per Watch run, lower is better; a green dot means the lesson was kept, a red dot means it was dropped), the list of lessons with "learned", "dropped" or "trying next", and a "Forget everything" button.
- **Ending screen:** a new "What the team learned" box for that run.
- **Event log:** lesson events appear under the "Adaptation" filter and as a pop-up.

## How to show it

- Main menu: show the Team Journal.
- During a Watch run: Team tab, then "Look inside Meera's head". Point to the purple bubble on the bridge and the ghosts at the harbour.

## Testing

- Frontend tests check the panel (who chose, options, "Show everything"), the "Look inside" button and the lesson labels.
- All 35 frontend tests pass, and the production build works.

## Files I worked on

- frontend/src/components/MindPanel.tsx (new Mind View panel)
- frontend/src/components/TeamPanel.tsx (the "Look inside" button)
- frontend/src/game/IslandScene.ts (purple bubbles and ghosts on the map)
- frontend/src/components/TeamJournal.tsx (journal card and learning curve)
- frontend/src/pages/MainMenu.tsx, EndingScreen.tsx, GameScreen.tsx (placing them on the screens)
