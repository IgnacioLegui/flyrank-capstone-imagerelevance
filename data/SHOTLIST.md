# Image shot list — 50 images

**How to use**
1. Search the query on [Unsplash](https://unsplash.com) or [Pexels](https://www.pexels.com) (both free
   licenses, no account needed to download).
2. Download any reasonable size and save it into `data/raw/` with **exactly** the filename in the table
   (any extension is fine: `.jpg`, `.jpeg`, `.png`, `.webp` — the resize script normalises to `.jpg`).
3. Note the photo's page URL and photographer — you'll paste them into `data/images/CREDITS.md`.
4. Run `.venv\Scripts\python scripts/resize_images.py`. It reads the filenames from this file, reports
   anything missing or unexpected, and writes resized copies to `data/images/`.

**Filenames are for humans and evaluation labels only.** The prefix matches the taxonomy key
(`red_fox_…` ↔ `SubjectKey.RED_FOX`) so labeling is easy, but the pipeline never uses filenames to match:
the vision model sees only the pixels.

**What makes a good pick:** the subject is clearly the main thing in the frame, unless the note says
otherwise. Variety within a subject (setting, season, pose) matters — later eval posts will describe
specific scenes ("a fox hunting in snow"), so each row has a distinct scene.

## Animals (24)

### Red fox (6)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 1 | `red_fox_01.jpg` | Red fox standing in a forest | `red fox forest` |
| 2 | `red_fox_02.jpg` | Red fox in snow (ideally mid-pounce / hunting) | `red fox snow` |
| 3 | `red_fox_03.jpg` | Close-up portrait of a red fox's face | `red fox portrait` |
| 4 | `red_fox_04.jpg` | Fox cub / kit | `fox cub` |
| 5 | `red_fox_05.jpg` | Red fox in a grassy meadow or field | `red fox meadow` |
| 6 | `red_fox_06.jpg` | Red fox curled up sleeping or resting | `red fox sleeping` |

### Gray wolf (5) — look-alikes for the fox (the guard must reject these on fox posts)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 7 | `gray_wolf_01.jpg` | Gray wolf standing in a forest (same setting as fox 01 — deliberate) | `gray wolf forest` |
| 8 | `gray_wolf_02.jpg` | Wolf in snow | `wolf snow` |
| 9 | `gray_wolf_03.jpg` | Wolf howling | `wolf howling` |
| 10 | `gray_wolf_04.jpg` | Close-up portrait of a wolf's face | `wolf portrait` |
| 11 | `gray_wolf_05.jpg` | Two or more wolves (pack) | `wolf pack` |

### Dog (5) — includes fox-coloured breeds on purpose
| # | Save as | Look for | Search query |
|---|---|---|---|
| 12 | `dog_01.jpg` | Shiba Inu (red/orange coat, very fox-like) | `shiba inu` |
| 13 | `dog_02.jpg` | Red/copper Siberian Husky | `red husky` |
| 14 | `dog_03.jpg` | Corgi (orange-and-white) | `corgi` |
| 15 | `dog_04.jpg` | Golden retriever outdoors | `golden retriever` |
| 16 | `dog_05.jpg` | Dog playing in snow | `dog snow` |

### Brown bear (4)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 17 | `brown_bear_01.jpg` | Brown bear catching salmon in a river | `brown bear salmon` |
| 18 | `brown_bear_02.jpg` | Brown bear walking in a meadow | `grizzly bear meadow` |
| 19 | `brown_bear_03.jpg` | Bear cub | `brown bear cub` |
| 20 | `brown_bear_04.jpg` | Bear standing on hind legs | `bear standing` |

### Deer (4)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 21 | `deer_01.jpg` | Stag with large antlers | `stag antlers` |
| 22 | `deer_02.jpg` | Doe in a forest | `deer forest` |
| 23 | `deer_03.jpg` | Fawn (spotted baby deer) | `fawn` |
| 24 | `deer_04.jpg` | Deer in snow | `deer snow` |

## Food (8)

### Pizza (4)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 25 | `pizza_01.jpg` | Margherita pizza, whole | `margherita pizza` |
| 26 | `pizza_02.jpg` | Pepperoni slice being lifted (cheese pull) | `pepperoni pizza slice` |
| 27 | `pizza_03.jpg` | Pizza in a wood-fired oven | `wood fired pizza oven` |
| 28 | `pizza_04.jpg` | Overhead shot of pizzas on a table | `pizza top view` |

### Coffee (4)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 29 | `coffee_01.jpg` | Latte with latte art | `latte art` |
| 30 | `coffee_02.jpg` | Espresso shot / espresso machine pouring | `espresso` |
| 31 | `coffee_03.jpg` | Roasted coffee beans | `coffee beans` |
| 32 | `coffee_04.jpg` | Iced coffee in a glass | `iced coffee` |

## Landscapes (8)

### Mountain (4)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 33 | `mountain_01.jpg` | Snow-capped peak | `snowy mountain peak` |
| 34 | `mountain_02.jpg` | Mountains reflected in an alpine lake | `alpine lake mountains` |
| 35 | `mountain_03.jpg` | Mountain range at sunset | `mountain sunset` |
| 36 | `mountain_04.jpg` | Hiking trail with mountains behind | `mountain hiking trail` |

### Beach (4)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 37 | `beach_01.jpg` | Tropical beach with palm trees | `tropical beach palm` |
| 38 | `beach_02.jpg` | Waves breaking on the shore | `beach waves` |
| 39 | `beach_03.jpg` | Rocky beach / coastline | `rocky beach` |
| 40 | `beach_04.jpg` | Beach at sunset | `beach sunset` |

## Vehicles (8)

### Bicycle (4)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 41 | `bicycle_01.jpg` | Road bike (side view, whole bike visible) | `road bike` |
| 42 | `bicycle_02.jpg` | Bicycle parked against a wall | `bicycle parked wall` |
| 43 | `bicycle_03.jpg` | Mountain biker on a dirt trail | `mountain biking` |
| 44 | `bicycle_04.jpg` | Vintage bicycle with a basket | `vintage bicycle basket` |

### Car (4)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 45 | `car_01.jpg` | Red sports car | `red sports car` |
| 46 | `car_02.jpg` | Classic / vintage car | `vintage car` |
| 47 | `car_03.jpg` | Car driving on a highway or road | `car on road` |
| 48 | `car_04.jpg` | Electric car charging | `electric car charging` |

## Deliberately ambiguous (2) — should be **flagged** as low-confidence (Probe 1)
| # | Save as | Look for | Search query |
|---|---|---|---|
| 49 | `ambiguous_01.jpg` | Heavily motion-blurred or out-of-focus shot where you genuinely can't tell what it is | `abstract blur` |
| 50 | `ambiguous_02.jpg` | Extreme macro of orange fur or an abstract texture — could be fox, dog, or a rug | `orange fur texture macro` |

> If the vision model turns out to be confident about an "ambiguous" pick, that's useful information,
> not a failure — we'll swap in something murkier in Phase 2 and log it in BUILDLOG.
