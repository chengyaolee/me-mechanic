# Geometry and NPR pipeline

## Current implementation

`blender/build_aventador.py` is the single source: it models every part, writes the GLB and the `src/aventador-parts.json` manifest (stable ID, zone, collection, removal dependencies, explosion vector, motion). `src/Scene.tsx` loads the GLB, matches meshes to manifest ids and renders painted panels with a clear-coated physical material; mechanical parts use the custom shader. `src/mechanics.mjs` holds the tested crank-train math. Scene metres, Y up, Z forward, ground at y=0; the engine is behind the cockpit at negative Z.

Painted panels use Rosso Mars `#D40000`, smooth physical lighting, clearcoat and Three.js output color conversion. They bypass the technical hatching shader. Body crease overlays appear only for selection, hover or faded context. A hemisphere and three directional lights provide studio lighting without external environment assets.

For mechanical parts, the current vertex shader transforms normals to view space. The fragment shader quantizes directional illumination into four bands and overlays diagonal screen-space hatch strokes. `Edges` generates angle-threshold crease lines; transparent shells disable depth writing but remain available for hover and selection. This is a real GLSL pipeline, but not yet a Sobel normal/depth compositor. Screen-space hatching can swim during orbiting, and the light is camera-relative.

## Production GLB contract

1. Obtain or author a mechanically partitioned asset with an explicit redistribution license. A single welded exterior mesh cannot support meaningful teardown. Keep license and provenance beside the source asset.
2. In Blender, use meters and apply scale. Preserve actual assembly coordinates and pivots; place crank/cam pivots on shaft axes, wheel pivots on hub centers, and piston pivots at crown centers. Match each exported mesh name to a registry ID. Keep mechanical groups separate from render submeshes.
3. Export a non-compressed development GLB first. Validate naming, units, axes, normals, disconnected meshes and local/world transforms before compression. Start with engine internals because motion makes pivot mistakes obvious.
4. Move registry metadata into `public/models/parts-manifest.json`, version it alongside the asset, and retain typed parsing at the boundary. Add `parentId`, `removalAxis`, full `specs`, rest transforms and optional kinematic axis. Distinguish removal axes from explosion layout vectors.
5. Load with Three.js `GLTFLoader` and `DRACOLoader`. Host the matching Draco decoder files locally; avoid a runtime CDN requirement. Traverse meshes once, validate duplicate/missing IDs, clone shared materials, then mount every mesh under a stable mechanical transform wrapper. Preserve `matrixWorld` when reparenting; never stack assembly coordinates twice.
6. Keep separate transforms for rest pose, explosion/removal and kinematics. Animate the outer wrapper for removal and the inner joint for operation. Cache geometry, crease edges and shader materials; dispose replaced assets. Retain the procedural model as a load-error fallback with a visible error message.
7. Compress after validation with glTF Transform/Draco. Compare decoded bounds and mesh names with the uncompressed baseline. Start with a 15 MB delivery budget and profile on integrated laptop graphics; budgets are project targets, not measured results.

## Shader upgrades

- Replace view-space illumination with world-space cool-shadow/warm-light Gooch tones, with a palette uniform for paper and blueprint themes.
- Replace screen-space stripes with object-space triplanar hatching; use derivatives for antialiasing. Maintain apparent line density while zooming.
- Render a normal/depth target for silhouette detection. Sobel-filter neighboring normals and linearized depth; scale thresholds with camera projection and resolution. Composite outlines after tone shading.
- Give selected objects a separate mask for stable pixel-width outlines; geometry edges alone do not capture smooth silhouettes.
- Ghost materials should retain faint Fresnel rims, omit normal/depth occlusion contributions, and bypass interaction. Avoid transparent surface sorting artifacts by controlling the shell render pass.
- Test color management and output transforms explicitly for ShaderMaterial; verify both themes in the actual browser. Add WebGL context-loss/error handling before production release.

## Mechanical validation before calling this engineering-accurate

Replace illustrative crank phases with verified firing order and crank geometry; add rods with exact endpoint constraints. Model the Aventador's actual pushrod suspension linkage and steering geometry. Validate the ISR ratios, final drives and front/rear coupling before presenting drivetrain readouts as factory values. Review every removal prerequisite for cycles, missing IDs and actual service order. Add failure/tuning notes only with model-specific evidence.

## Acceptance checks

Orbit completely beneath the chassis; switch projections while zoomed; select internal parts through ghost shells; remove/reinstall during motion; reverse explosion mid-transition; inspect at narrow mobile widths; test without WebGL; verify shader compilation and console errors; profile draw calls and interaction latency. These browser checks remain pending in the current environment.
