# me-mechanic

A pure frontend automotive anatomy workbench, built with Vite, React, TypeScript, React Three Fiber, Drei, Three.js and Zustand. The initial study is inspired by the Lamborghini Aventador LP 700–4.

## Run

```sh
npm install
npm run dev
npm test
npm run build
npm run verify:parts
```

Deploy `dist/` on a static host. No API keys or backend required.

## Model

`blender/build_aventador.py` builds the whole car in Blender as **431 separately named parts**, each with its own material and its origin on its real pivot (hub centre, crank axis, wrist pin, door and cover hinges). The parts are organised in collections that the GLB keeps as named empties:

| Collection | Contents |
|---|---|
| `01_Exterior_Body` | Lofted body panels, glass, hinged glass engine cover with struts, scissor doors with glass and mirrors, front lid, lamps, louvres, active wing |
| `02_Chassis_Monocoque` | Carbon tub (floor, sills, tunnel, bulkheads, pillars), aluminium front and rear frames, crash boxes, engine mounts |
| `03_Powertrain` | L539 V12: block halves, bedplate, dry sump, 7 main caps, 12 liners, heads, cam covers, 4 camshafts with lobes, sprockets, chains, 48 valves, valve springs, 12 plugs, coils, injectors, fuel rails, plenums, 12 runners, throttles, airboxes, 12 headers, collectors, cats, silencer, hex tailpipe, radiators, fans, pumps, oil tank, accessory drive, crank, 12 pistons, 12 rods, flywheel, clutch; 7-speed ISR gearbox with gear pairs and shift actuator; propshaft, Haldex, front and rear differentials, half-shafts |
| `04_Suspension_Brakes` | Per corner: tyre, forged wheel, bolts, hub, upright, carbon-ceramic disc, caliper, pads, both wishbones, pushrod, rocker, horizontal damper, spring, tie rod or toe link, brake line; anti-roll bars, steering rack and column |
| `05_Aero_Underbody` | Splitter, undertray, floor, diffuser and strakes, arch liners, heat shield |
| `06_Interior` / `07_Electrical` | Seats, belts, steering wheel, paddles, dash, TFT cluster, console, start-button flap, pedals; battery, fuel tank and pump, ECUs, cabling |

```sh
npm run assets   # blender -b -P blender/build_aventador.py  (BLENDER=/path/to/blender to override)
```

This writes `blender/aventador.blend` (realistic materials, for stills and ads), `public/models/aventador.glb` and `src/aventador-parts.json` (names, descriptions, removal order, explode vectors and motion for each part). Add `-- --render <dir>` for Workbench check renders.

## App

Hover any part to preview its details in the right panel. In the model or assembly index, the first click selects, the second click zooms to the component and fades surrounding parts, and clicking the focused component again restores the prior camera and normal opacity. Removing a focused component also clears focus. Clicking empty canvas clears selection and focus. Clicking another component switches selection. Hovering components in the model or index updates the right panel in every state; workshop actions remain tied to the selected component. The clear-selection control clears both selection and focus. Explicit controls open the glass cover, scissor doors and front lid; the reveal control lifts the V12 in staged layers. The assembly index, depth peel, explode slider, dependency-checked removal, camera bookmarks, and the running engine (12 pistons and rods solved from the crank angle, cams at half speed, gearbox, driveline, wheels, steering, dampers) all drive the Blender parts.

## Component verification

[PARTS_VERIFICATION.md](PARTS_VERIFICATION.md) records corrected metadata, unresolved geometry discrepancies and missing systems. The [431-row inventory](reports/component-inventory.csv) checks every component group against its GLB mesh. `npm run verify:parts` repeats the asset checks. Matching meshes do not establish a complete or factory-accurate vehicle inventory.

## Accuracy boundary

This is a reconstructed teaching model, not an OEM CAD model, workshop guide, vehicle simulator or validated engineering model. Shape, clearances, connecting-rod length (145 mm), gear/final-drive ratios, teardown dependencies and component materials are illustrative. Body panels are shaped reconstructions; exact OEM surface contours remain unverified. Steering and suspension motion are demonstrations, not a solved linkage. Valves do not yet follow the cam lobes; gear teeth, wiring harnesses and fasteners below wheel-bolt size are not modelled. Internal packaging (accessory drive, radiator and tank positions, pipe routes) is a plausible reconstruction. Full-speed motion can alias at screen refresh rates; the 10 RPM visualization mode preserves numerical engine-speed readouts while slowing geometry.

The V12 uses 60° banks and 76.4 mm stroke. Factory references: [Lamborghini launch press kit](https://www.ausmotive.com/downloads/Lamborghini/Aventador-full-release-Mar2011.pdf) (manufacturer document mirrored by Ausmotive), specifying 6,498 cm³, 95 × 76.4 mm bore/stroke and dry-sump lubrication. No licensed Lamborghini mesh, logos or third-party model is bundled. This is an independent project.

## Public repository setup

From this directory, in a terminal permitted to write Git metadata:

```sh
gh auth login -h github.com
git init -b main
git add .
git commit -m "Build Aventador anatomy prototype"
gh repo create me-mechanic --public --source=. --remote=origin --push
```

See [ASSET_PIPELINE.md](ASSET_PIPELINE.md) for the shader stage and for swapping in a licensed production mesh.
