# When a chapter is meant to sound different

By [Matthias Fahsold](https://github.com/mfahsold) · Published 19 October 2026 · 4 minutes

A letter interrupts your narrator's voice. A child's account uses shorter sentences. An official record becomes formal and dense. These chapters may stand out in a style comparison for exactly the reason you wrote them. In Lixity, a **chapter register** records that deliberate difference: you name the register, assign a chapter and optionally describe the feature ranges you want to review.

The setting expresses your intention. It cannot discover the voice you meant, certify its authenticity or decide whether the chapter works. Its practical value is a more explicit review: you can keep the measurements while changing how an intentionally different chapter enters the shortlist.

## Read the difference before labelling it

Imagine chapter 3 consists of a letter. Its sentences run longer than those in the surrounding narration. Before assigning a register, read the chapter and ask what those longer sentences do. Perhaps they sustain the letter writer's elaborate manner. Perhaps one paragraph simply lost its shape. Both explanations can produce the same numerical difference.

Lixity's book reference describes measurable features across the manuscript's eligible chapters. It is useful for finding departures from that local pattern; it supplies no universal ideal for a letter. Assign `letter` after reviewing the reason for the difference, and keep checking individual passages inside it.

## Record the decision in the local workspace

Chapter registers are available in Lixity 0.5.0. With your manuscript's project open in the native local workspace:

1. Open **Project → Settings → Chapter registers**. Choose **Add register** and enter `letter` as its name.

2. Choose **Assign chapter**. Enter `3` as the chapter selector and `letter` as the register name. A number selects that chapter exactly; a full chapter title is another option.

3. Leave the register without targets if the label captures your decision. To describe an additional comparison, choose **Add range**, select the feature and enter a lower bound, an upper bound or both.

4. Choose **Apply**. Lixity validates the settings, rebuilds the analysis and saves the register definitions and assignments together in the selected project's `lixity.toml`.

5. Return to the chapter comparison. Look for the register label; if you added targets, review their measured values and whether they fall below, within or above your range. A measurement can also be unavailable.

If the project or its saved settings changed while you were editing, reload and review the current settings before applying your changes again. Revisit assignments after renumbering chapters or restructuring the manuscript: the setting should continue to describe the chapter you intended.

## Use ranges only when they help a decision

For this invented letter, suppose you want to inspect a mean sentence length between 18 and 30 words. The equivalent project configuration is:

```
[register_profiles.letter]
asl = { lower = 18, upper = 30 }

[chapter_registers]
"3" = "letter"
```

`asl` means average sentence length in words. These bounds are invented for this example, with no claim about historical letters or desirable prose. A value within them only answers whether the measured mean falls in your chosen interval. It cannot tell you whether a particular sentence is clear, or whether the voice convinces a reader. The usual measurement floors still apply.

## Understand the flag you are setting aside

**An assigned chapter is excluded from chapter deviation and FDR flags.** That exclusion covers the chapter, including features for which you supplied no target. It can therefore remove a flag that might otherwise have helped you notice an accidental change.

The descriptive information remains: measured values, book-relative z-scores, membership in the book baseline and the consistency summary. Your ranges sit alongside that reference; they do not recalculate it or create a new statistical score. Paragraph tense flags serve a separate review purpose.

Use the assignment to record a reviewed intention, then read the result. A formal document can still contain an awkward paragraph. A child's voice can still drift. Statistical signals and author ranges make those questions easier to locate; neither establishes literary quality.

## Set up one deliberate contrast

Start with a single chapter whose different voice you can explain in words. A label alone may be sufficient. The [chapter register reference](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md#chapter-register-settings) gives the supported range forms and chapter matching rules when you are ready to configure it. The public demo is read-only; saving register settings requires the native local workspace.

[Lixity home](../) · [Blog](index.html) · [Report a reproducible issue](https://github.com/mfahsold/lixity/issues) · [Legal notice](../#impressum)
