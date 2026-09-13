import {
  buildMultiChatHandoff,
  buildMultiChatTranscript,
  stripVariablesSection,
} from 'd:/vishnu bhagwan/hanuman/New folder/download (1)/projects/projects/Prompt_Enhancer-FE/src/features/chat/services/multiChatExportService.ts';

const snippetWithVars = `ROLE:** Senior Screenplay Consultant
TASK: Write a screenplay draft.

4. Sound Design Notes (3 critical audio elements, frequency/duration/purpose):
   - Example:
     - "The garden’s hum (100Hz, 30 seconds, subliminal)."
5. Practical Effects Breakdown (If {{PRACTICALEFFECTSBUDGET}} is provided):
   - Example:
     - "Limited to 5 practical plants—prioritize the seedling and the glowing leaf for maximum impact."

VARIABLES TO FILL (IF USER PROVIDES):
- {{USERSPECIFICCHARACTER_BACKSTORY}} → "His daughter died in a car accident; he blames himself."
- {{PRACTICALEFFECTSBUDGET}} → "Limited to 3 practical plants—use slow-motion for maximum effect."
- {{TONE_ADJUSTMENT}} → "Lean harder into existential dread" or "Add a touch of melancholic hope."`;

console.log("=== RAW TEST OF stripVariablesSection ===");
const stripped = stripVariablesSection(snippetWithVars);
console.log("Contains 'VARIABLES TO FILL':", stripped.includes("VARIABLES TO FILL"));
console.log("Contains 'Sound Design Notes':", stripped.includes("Sound Design Notes"));

const sampleItem = {
  id: 'test-1',
  title: 'Martian Garden',
  originalPrompt: 'Write a sci-fi short film script about a Martian garden.',
  mode: 'Cinematic',
  versions: [
    {
      versionNumber: 1,
      optimizedPrompt: 'Version 1 prompt content.',
    },
    {
      versionNumber: 2,
      optimizedPrompt: snippetWithVars,
      tweakNote: 'Re-enhanced from v1.',
    },
  ],
};

console.log("\n=== TEST buildMultiChatHandoff (TXT) ===");
const handoffTxt = buildMultiChatHandoff([sampleItem], 'txt');
console.log("Handoff TXT has 'VARIABLES TO FILL':", handoffTxt.includes("VARIABLES TO FILL"));
console.log("Handoff TXT has 'Sound Design Notes':", handoffTxt.includes("Sound Design Notes"));

console.log("\n=== TEST buildMultiChatHandoff (MD) ===");
const handoffMd = buildMultiChatHandoff([sampleItem], 'md');
console.log("Handoff MD has 'VARIABLES TO FILL':", handoffMd.includes("VARIABLES TO FILL"));

console.log("\n=== TEST buildMultiChatTranscript ===");
const transcriptTxt = buildMultiChatTranscript([sampleItem], 'txt');
console.log("Transcript TXT has 'VARIABLES TO FILL':", transcriptTxt.includes("VARIABLES TO FILL"));
