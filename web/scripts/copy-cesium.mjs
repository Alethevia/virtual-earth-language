import { cpSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root = new URL('../', import.meta.url);
const dest = new URL('public/cesium/', root);
mkdirSync(dest, { recursive: true });
cpSync(new URL('node_modules/cesium/Build/Cesium/', root), dest, { recursive: true });
