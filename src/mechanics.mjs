export const blockers = (part, removed) => part.blockedBy.filter(id=>!removed.includes(id));
export const ratios = [0,3.91,2.44,1.81,1.46,1.19,.97,.84]; // illustrative ratios, not verified OEM data
// Crank-train pose of one cylinder at crank angle theta (rad); same geometry as blender/build_aventador.py.
// The crank turns about +z, so a throw at angle `throw` (clockwise from +y, degrees) sits at throw - theta.
export const crankPose = (k, theta) => {
 const r=k.stroke/2, a=k.throw*Math.PI/180-theta, b=k.bank*Math.PI/180, [x,y,z]=k.centre, phi=a-b;
 const s=r*Math.cos(phi)+Math.sqrt(k.rod*k.rod-(r*Math.sin(phi))**2);
 return {pin:[x+r*Math.sin(a),y+r*Math.cos(a),z],wrist:[x+s*Math.sin(b),y+s*Math.cos(b),z]};
};
// Top assemblies lead; lower assemblies wait for clearance in the reveal.
export const revealProgress = (progress, height) => {
 const delay=Math.max(0,Math.min(.45,(1.8-height)*.3));
 const t=Math.max(0,Math.min(1,(progress-delay)/(1-delay)));
 return t*t*(3-2*t);
};

// Focus overrides every peel layer, including glass: the target stays solid.
export const partAppearance = (part, focusedId, peeled = false) => {
 if (part.id === focusedId) return {alpha:1, edgeOpacity:1};
 if (focusedId) return {alpha:.025, edgeOpacity:.06};
 return {alpha:peeled?.07:part.tone==='glass'?.28:1, edgeOpacity:peeled?.12:part.tone==='glass'?.45:.85};
};

// Let the focused solid receive clicks through transparent shells while keeping
// all other parts pickable and hoverable outside its silhouette.
export const prioritizeFocusedHits = (hits, focusedId) => {
 if (!focusedId) return hits;
 return [...hits.filter(hit=>hit.object.name===focusedId), ...hits.filter(hit=>hit.object.name!==focusedId)];
};
