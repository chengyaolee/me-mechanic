import fs from 'node:fs';
import assert from 'node:assert/strict';
const root = new URL('../', import.meta.url);
const manifest = JSON.parse(fs.readFileSync(new URL('src/aventador-parts.json', root)));
const bytes = fs.readFileSync(new URL('public/models/aventador.glb', root));
assert.equal(bytes.toString('ascii', 0, 4), 'glTF');
assert.equal(bytes.readUInt32LE(4), 2);
assert.equal(bytes.readUInt32LE(8), bytes.length);
assert.equal(bytes.toString('ascii', 16, 20), 'JSON');
const gltf = JSON.parse(bytes.toString('utf8', 20, 20 + bytes.readUInt32LE(12)));
const nodes = gltf.nodes.filter(n => n.mesh !== undefined);
const ids = new Map(manifest.parts.map(p => [p.id, p]));
assert.equal(ids.size, manifest.parts.length, 'Duplicate component IDs');
assert.equal(new Set(nodes.map(n => n.name)).size, nodes.length, 'Duplicate mesh names');
assert.deepEqual(nodes.map(n => n.name).sort(), [...ids.keys()].sort(), 'Model / list mismatch');
for (const n of nodes) {
 const mesh = gltf.meshes[n.mesh];
 assert.ok(mesh.primitives.length, `${n.name}: no geometry`);
 for (const primitive of mesh.primitives) {
  const positions = gltf.accessors[primitive.attributes.POSITION];
  assert.ok(positions.count >= 3, `${n.name}: empty mesh`);
  assert.ok([...positions.min, ...positions.max].every(Number.isFinite), `${n.name}: invalid bounds`);
  assert.ok(positions.max.some((v, i) => v > positions.min[i]), `${n.name}: collapsed geometry`);
 }
}
const visited = new Set(), visiting = new Set();
function visit(id) {
 assert.ok(ids.has(id), `Unknown prerequisite: ${id}`);
 assert.ok(!visiting.has(id), `Dependency cycle: ${id}`);
 if (visited.has(id)) return;
 visiting.add(id);
 ids.get(id).blockedBy.forEach(visit);
 visiting.delete(id); visited.add(id);
}
ids.forEach(p => {assert.ok(manifest.zones.includes(p.zone), p.id); visit(p.id);});
for (const [pattern, count] of [[/^piston[AB]\d$/,12],[/^rod[AB]\d$/,12],[/^valve[AB]\d\d$/,48],[/^cam[AB](Intake|Exhaust)$/,4],[/^radiator[LR]$/,2],[/^(lowerArm|upperArm)[FR][LR]$/,8],[/^pushrod[FR][LR]$/,4],[/^rocker[FR][LR]$/,4],[/^damper[FR][LR]$/,4]]) {
 assert.equal([...ids.keys()].filter(id => pattern.test(id)).length, count, `${pattern}: component count`);
}
for (const id of ['crank','waterPump','oilTank','scavengePump','oilCooler','gearboxCase','frontDiff','rearDiff','steeringRack']) assert.ok(ids.has(id), id);
const csv = [['id','name','zone','assembly','mesh_check','accuracy'], ...manifest.parts.map(p => [p.id,p.name,p.zone,p.assembly,'matched; nonempty geometry','reconstruction; exact geometry and fit unverified'])].map(row => row.map(v => '"'+v.replaceAll('"','""')+'"').join(',')).join('\n')+'\n';
if (process.argv.includes('--write')) fs.writeFileSync(new URL('reports/component-inventory.csv', root), csv);
console.log(`Verified ${ids.size} component groups against ${nodes.length} GLB mesh nodes: unique IDs, matching names, nonempty geometry, valid zones and acyclic dependencies. Factory completeness is not established; see PARTS_VERIFICATION.md.`);
