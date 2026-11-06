'use strict';
const assert = require('node:assert/strict');
const {checked} = require('../docs/simulation_v2.js');
const p = {schema_version:2,model:'paper-execution-v2',simulation_only:true,accounts:[{id:'stock',availability:'BLOCKED',reason:'Unresolved legacy ledger'}]};
assert.equal(checked(p)[0].availability,'BLOCKED');
for (const value of [null,{}, {...p,simulation_only:false},{...p,accounts:[...p.accounts,...p.accounts]},{...p,accounts:[{...p.accounts[0],availability:'SAVED_SIMULATION'}]}]) assert.throws(() => checked(value));
console.log('V2 simulation schema, missing evidence and duplicate-account checks passed.');
