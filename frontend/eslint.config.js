import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  // src/features/_pending GECICI: tsconfig'in exclude'uyla ayni sebeple burada.
  // Henuz tasinmamis feature'lar eski mission/overlay modullerini import
  // ediyor; ikisi de kalkinca bu giris de silinir.
  { ignores: ['dist', 'node_modules', 'public', 'src/features/_pending'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    // Bu iki hook kurali bu config'in var olma sebebi: bagimlilik listeleri
    // yanlis yazildiginda TypeScript derlenir, uygulama acilir, ama panel ya
    // eski veriyi gosterir ya da sonsuz donguye girip istekleri arka arkaya
    // atar. Ikisi de 'error' -- lint zaten --max-warnings 0 ile kostugu icin
    // pratik fark yok, ama niyet aciktan okunuyor.
    //
    // eslint-plugin-react-hooks 7'nin kendi "recommended" seti bunlarin
    // yaninda React Compiler kurallarini da acar (purity, immutability,
    // set-state-in-effect, refs...). Onlari bilerek almiyoruz: TerrainCanvas3D
    // three.js'i dogrudan imperatif surer ve App.tsx'in efektleri o kurallara
    // gore bastan yazilmak zorunda kalirdi. Acmak isteyen asagidaki iki satiri
    // ...reactHooks.configs.recommended.rules ile degistirir ve cikan ~6 hatayi
    // refactor eder.
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'error',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },
)
