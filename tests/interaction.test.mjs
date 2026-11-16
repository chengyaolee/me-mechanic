import {test} from 'node:test';
import assert from 'node:assert/strict';
import {useStore} from '../src/store.ts';
import {partAppearance,prioritizeFocusedHits} from '../src/mechanics.mjs';

test('selection, focus, switching, removal and reset share consistent transitions',()=>{
 const initial=useStore.getState();
 const state=()=>useStore.getState();
 try {
  state().set({selected:null,focused:null,removed:[]});
  state().clickPart('crank');
  assert.equal(state().selected,'crank');
  assert.equal(state().focused,null,'first click only selects');
  assert.equal(partAppearance({id:'blockA',tone:'metal'},state().focused).alpha,1);
  state().clickPart('crank');
  assert.equal(state().focused,'crank','second click focuses');
  assert.ok(partAppearance({id:'blockA',tone:'metal'},state().focused).alpha<.05);
  state().clickPart('crank');
  assert.equal(state().focused,null,'clicking the focused part unfocuses');
  assert.equal(state().selected,'crank','unfocus preserves selection');
  state().clickPart('crank');
  state().clickPart('radiatorL');
  assert.equal(state().selected,'radiatorL');
  assert.equal(state().focused,null,'switching parts starts with selection');
  state().clickPart('radiatorL');
  assert.equal(state().focused,'radiatorL');
  state().set({removed:['radiatorL']});
  assert.equal(state().focused,null,'removing the focused part clears focus');
  state().clickPart('radiatorL');
  assert.equal(state().focused,null,'removed parts cannot receive focus');
  state().set({removed:[]});
  state().clickPart('radiatorL');
  assert.equal(state().focused,'radiatorL','reinstalled parts can receive focus');
  state().set({focused:null});
  assert.equal(state().selected,'radiatorL','clear focus keeps the inspected component');
  state().clickPart('radiatorL');
  state().clearSelection();
  assert.equal(state().focused,null);
  assert.equal(state().selected,null);
  state().clickPart('crank');
  state().set({hovered:'radiatorL'});
  assert.equal(state().selected,'crank','hover leaves selection intact');
  assert.equal(state().hovered,'radiatorL');
  state().clickPart('crank');
  state().set({hovered:'waterPump'});
  assert.equal(state().focused,'crank','hover leaves focus intact');
  assert.equal(state().hovered,'waterPump');
  state().clearSelection();
  assert.equal(state().selected,null,'background clears selection');
  assert.equal(state().focused,null,'background clears focus');
  assert.equal(state().hovered,null,'background clears hover details');
  // Hinged panels follow the same click contract; explicit controls open them.
  state().clickPart('doorL');
  assert.equal(state().doorsOpen,false);
  assert.equal(state().focused,null);
  state().clickPart('doorL');
  assert.equal(state().focused,'doorL');
  assert.equal(state().doorsOpen,false);
 } finally {useStore.setState(initial);}
});

// Transparent shells must not trap focus, and other hits must remain available.
test('focus hit ordering preserves all other hover and selection targets',()=>{
 const shell={object:{name:'glassCover'}}, crank={object:{name:'crank'}}, radiator={object:{name:'radiatorL'}};
 const hits=[shell,crank,radiator];
 assert.deepEqual(prioritizeFocusedHits(hits,'crank'),[crank,shell,radiator]);
 assert.deepEqual(hits,[shell,crank,radiator],'does not mutate raycast results');
 assert.deepEqual(prioritizeFocusedHits([shell,radiator],'crank'),[shell,radiator],'other parts remain pickable outside focused silhouette');
 assert.equal(prioritizeFocusedHits(hits,null),hits,'selection alone preserves normal hit order');
});
