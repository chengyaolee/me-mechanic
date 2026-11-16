# Aventador LP 700–4 component verification

Scope: the current reconstructed coupe model, not later Aventador S/SV/SVJ hardware. “Sant’Agata Bolognese” identifies Lamborghini’s location, not an additional model variant.

All **431 component groups** match **431 uniquely named GLB mesh nodes**. There are no missing or extra mesh IDs. Geometry is nonempty, and removal dependencies refer to existing IDs without cycles. These checks establish asset consistency; they do not establish factory accuracy or a complete vehicle bill of materials.

The [complete component inventory](reports/component-inventory.csv) lists every current component and its mesh check. Run `npm run verify:parts` to repeat the checks, or `node scripts/verify-parts.mjs --write` to refresh the inventory.

## Reference

[Lamborghini’s March 2011 launch press kit, mirrored by Ausmotive](https://www.ausmotive.com/downloads/Lamborghini/Aventador-full-release-Mar2011.pdf), especially printed pages 14–21 and 25–28. It is a manufacturer description, not an exploded service catalogue. No VIN-specific OEM parts catalogue or engineering drawings were supplied, so individual part numbers, exact shapes, locations and fit remain unverified.

## Errors corrected

- Block descriptions called the crankcase closed deck. Corrected to open deck with steel liners.
- Eight wishbones were labelled steel. Corrected to aluminium.
- Front lid, front fenders and doors now identify aluminium; rear haunch and rocker-cover groups identify SMC; the roof identifies carbon fibre.
- The clutch and brake pads reused the brake-disc material label “Carbon-ceramic (CCB).” Removed that unsupported composition claim. The clutch specification records the published 235 mm diameter, with approximate geometry explicitly identified.
- Uprights were simultaneously described as forged and labelled cast. Removed the unverified manufacturing-process claim.
- Coil springs and the battery cable inherited paint-material descriptions. Replaced those with mechanical descriptions; cable construction remains unverified.
- Removed the unsupported front-luggage-bay fuel-filler claim. Tank geometry and position are explicitly identified as placeholders.

Metadata corrections are in the Blender generator and generated manifest, so regeneration preserves them.

## Coverage and remaining discrepancies

| System | Present in the current model | Gaps / accuracy limits |
|---|---|---|
| Crank train | Crankshaft, flywheel, 12 pistons, 12 rods, seven main-cap groups, 12 liners | Crank phases, firing order, journal profiles and clearances unverified. Rings, wrist pins, bearing shells, rod bolts and thrust washers are not independently selectable. Rod length is illustrative. |
| Heads / timing | Two heads, four cams, four sprockets, two chain groups, 48 valves, 12 spring groups, plugs and coils | Valve springs are grouped per cylinder. Guides, seats, retainers, collets, tappets/followers, tensioners, guides, VVT actuators, seals and fasteners are absent or not independently represented. Valves do not follow the cams. |
| Cylinder spacing | Six repeated cylinder stations per bank | Generator uses 100 mm spacing; published spacing is 103.5 mm. Geometry correction requires coordinated block, crank, cam, intake and exhaust repackaging; remains unresolved. |
| Cooling / lubrication | Left/right coolant radiator and fan groups, hoses, water pump, expansion tank, oil reservoir, scavenge-pump group and oil cooler | Cooler positions, sizes and hose routes remain illustrative. Separate thermostats, pressure pump, oil filter, oil/water exchanger and individual scavenging stages are not represented. |
| Intake / fuel / exhaust | Airboxes, throttles, plenums, 12 runners, injectors, rails, 12 headers, catalysts, silencer, outlet, tank and pump | Missing separate filters, sensors, lambda probes, exhaust actuators, evaporative-emissions hardware and full fuel lines. Front tank placeholder is only about 18 L by box volume and is not a credible production-capacity tank. Filler position is unverified. |
| Transmission / AWD | Twin-plate clutch group, gearbox case, seven gear pairs, shift actuator, shafts, Haldex and differentials, four half-shafts | Ratios, tooth counts, shaft speeds, hydraulic details and coupling behaviour are illustrative. Reverse gear, synchronizers, bearings and internal differential gears are not separate components. CV joints/boots are grouped into shafts. |
| Suspension / steering | Eight wishbones; four each of uprights, hubs, pushrods, rockers, horizontal dampers and springs; front tie rods, rear toe links, anti-roll bars, rack and column | Ball joints/bushes are grouped with arms, wheel bearings with hubs. Mount hardware and anti-roll links are incomplete. Spring/damper compression is a visual demonstration; wheel travel and linkage constraints are not solved. |
| Brakes / wheels | Four wheels, tyres, wheel-bolt groups, discs, calipers, pad groups and flexible lines | Master cylinder, reservoir, vacuum booster, ABS hydraulic unit, hard pipes, parking-brake hardware and wheel-speed sensors are absent. Five wheel bolts form one selectable group per corner. |
| Body / structure / aero | Panels, optional transparent engine cover, hinges, lights, monocoque subdivisions, subframes, engine mounts, underfloor and diffuser | Contours, structural joints and hinge axes are reconstructed. Tub subdivisions are visual groups, not verified removable panels. Lamps and mechanisms lack full internals; generic panel materials remain where unsupported. |
| Cabin / safety / HVAC | Seats, belts, wheel, paddles, dashboard, cluster, console and pedals; A/C compressor | Airbags, pretensioners, HVAC evaporator/condenser/blower, ducting, refrigerant circuit, window regulators, locks, audio and much trim are absent or grouped. |
| Electrical / controls | Battery, two ECU groups, fuse box and main cable | Full wiring, grounds, connectors, sensors, control modules, relays and actuators are incomplete. |

This is a partial teaching inventory, not “all parts verified.” The inventory CSV deliberately marks every shape and fit as unverified. Small visible shapes inside a combined mesh do not count as separate selectable parts. Teardown prerequisites are internally consistent but remain unvalidated service procedures.

## Interaction changes

Hover details and selected-part information occupy the right column outside the canvas, including at narrow widths. From either the model or assembly index, the first click selects without changing opacity or the camera. The second click zooms to the component and makes it opaque while surrounding components become faint transparent geometry with outlines. Clicking the focused part again clears focus and restores the prior camera. Removing it also clears focus. Focus overrides depth peel and glass transparency. Background clicks and “Clear selection / focus” clear both states. Clicking another part switches selection and exits focus. Hover previews remain active for all installed parts, including during focus, and show full details in the right panel; workshop actions remain tied to the selected component. Reset also clears selection and focus. Explicit controls open hinged panels and reveal engine internals.
