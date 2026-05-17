// Post-build script: copy static files into standalone output
const fs = require('fs');
const path = require('path');

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const f of fs.readdirSync(src)) {
    const s = path.join(src, f);
    const d = path.join(dest, f);
    if (fs.statSync(s).isDirectory()) {
      copyDir(s, d);
    } else {
      fs.copyFileSync(s, d);
    }
  }
}

copyDir('.next/static', '.next/standalone/.next/static');
copyDir('public', '.next/standalone/public');
console.log('Static files copied to standalone output.');
