---
layout: default
title: "Auditing 26 Android screens: 0% unlabeled, 17% tap targets too small"
---

# Auditing 26 Android screens: 0% unlabeled, 17% tap targets too small

A read-only audit of 26 Android screens (10 apps, 245 interactive controls) produced three numbers:
**0%** of controls are genuinely unlabeled, **9.5%** rely on an ancestor for their label, and
**17.1%** have tap targets between 24 and 48 dp. The measurements were taken with
`uiautomator dump`, so nothing was tapped, typed or submitted.

Along the way the metric was wrong three times: 90% → 10.2% → 0.8% → 0%.

## Method

`adb shell uiautomator dump` serialises the current screen into an XML tree where each node carries
`text`, `content-desc`, `bounds` and `clickable`. The file is deleted after parsing.

Three metrics:

| Metric | Definition |
|---|---|
| unlabeled | interactive control with no text in itself or its 4 nearest ancestors |
| undersized | interactive control narrower or shorter than 48 dp |
| no-interactive page | a page whose interactive control count is zero |

Sample: 26 screens, 10 apps, 245 interactive controls, Android 10, 1080×2340, density 480.

## Results

| Metric | Value |
|---|---|
| genuinely unlabeled | **0 (0.0%)** |
| label comes from an ancestor | **23 (9.5%)** |
| tap target 24–48 dp | **42 (17.1%)** |
| tap target < 24 dp (mostly decoration) | 6 |
| invisible (zero bounds) | 3 |
| pages with no interactive control | 1 (3.8%) |

## The metric was wrong three times

**1. 90%.** The first version asked whether the clickable node itself had text. On a settings screen,
9 of 9 interactive controls looked unlabeled. The tree showed why: clickable nodes are usually
containers (`LinearLayout`, `FrameLayout`) and the text lives on a child. A screen reader merges the
whole subtree. Counting "self or any descendant" dropped the number from 90%+ to **10.2%**.

Same data, different definition, one order of magnitude apart.

**2. 0.8%.** Grouping by control type showed 16 of the 24 "unlabeled" controls were switches. A
settings row is "title `TextView` + `Switch`": two sibling nodes linked by `android:labelFor`,
a relation `uiautomator dump` does not export. Adding a row-level rule (a switch inherits text from
its parent container) and excluding zero-size nodes brought it to **0.8%**.

**3. 0.0%.** The remaining SeekBar had its label four levels up. That is the real problem: "labeled or
not" is a binary question whose threshold is arbitrary. Measuring the **label distance** instead:

| distance | meaning | controls | share |
|---|---|---|---|
| 0 | own label | 219 | 90.5% |
| 1 | parent | 8 | 3.3% |
| 2 | grandparent | 14 | 5.8% |
| 4 | fourth ancestor | 1 | 0.4% |
| none | nothing within 4 | **0** | **0.0%** |

Two conclusions, both different from the first headline:

1. genuinely unlabeled controls: **0%** — nothing here is unreadable
2. but **9.5%** of labels live on an ancestor — where a screen reader can lose context

## Tap targets

Initially 21.3% of controls were under 48 dp. Inspecting the smallest ones:

```text
class            w(dp)  h(dp)
LinearLayout     360.0   18.7   <- divider row
SeekBar          312.0   40.0   <- real target: 40 dp thumb
SeekBar          312.0   40.0
LinearLayout     360.0   43.0
```

Anything under 24 dp is almost certainly decoration, so the metric was split into `undersized`
(24–48 dp) and `tiny` (<24 dp). The corrected figure is **17.1%**.

## Is the data source stable?

Eight consecutive dumps of one screen: node count constant at 107 (**0% jitter**), interactive count
constant at 12, mean dump time **1.86 s**. Stable enough for single samples; slow enough that 500
screens take 16 minutes. Scrolling one screen shifts the metrics by about **±7%**, so one dump per
page is a coarse filter only.

## Some screens expose nothing

A minimal web page (heading, two paragraphs, one link) produced:

```text
nodes=10   nodes with text=2   nodes with content-desc=0
interactive=1 (the link), unlabeled
```

A canvas-rendered screen is worse: 8 nodes, all decorative, **0 interactive**.

No parser can recover information the platform never exposes, so the tool grew a second channel:
screenshot geometry (connected components), normalised template matching for the selected state,
and OCR. Against the accessibility text as ground truth, OCR recall was **71.9%** (82/114 strings
over 7 pages, ranging 50–94%). OCR finds, vision verifies — not either/or.

## Fault injection: retries fix less than expected

| Fault | effective drop | success |
|---|---|---|
| clean | 0% | 100% |
| delay 500 ms | 0% | 100% |
| drop 30% | 14% | 100% |
| drop 60% | 21% | 0% |
| hide one anchor | 100% | 0% |

Delay costs nothing because the engine polls for state instead of sleeping. A persistently missing
anchor cannot be retried into existence — which is the argument for the second channel.

## Limits

- system settings and stock apps only; no third-party apps audited
- static screens; scrolling and animation not sampled
- OCR recall 71.9%; long lines are missed
- fault injection sample is small (n=4–5)
- vision is connected components + template matching, not general element detection

## Links

- Repository: [github.com/xuyuxu-dev/mobile-ui-a11y-demo](https://github.com/xuyuxu-dev/mobile-ui-a11y-demo)
- Chinese version: [中文实测报告](https://xuyuxu-dev.github.io/mobile-ui-a11y-demo/)