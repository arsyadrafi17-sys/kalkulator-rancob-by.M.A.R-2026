import React, { useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  Calculator,
  Download,
  FileText,
  ListFilter,
  MapPin,
  Sprout,
} from 'lucide-react';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { TabAnova } from './components/TabAnova';
import { TabExport } from './components/TabExport';
import { TabFieldMap } from './components/TabFieldMap';
import { TabMatrix } from './components/TabMatrix';
import { TabPostHoc } from './components/TabPostHoc';
import { TabSteps } from './components/TabSteps';
import { TabSubSamples } from './components/TabSubSamples';
import { TreatmentNameModal } from './components/TreatmentNameModal';
import { PRESETS } from './data/presets';
import { DesignConfig, DesignType, PostHocType } from './types';
import { calculateAnova } from './utils/anovaCalculations';
import { exportToExcel } from './utils/excelExporter';
import { generateTreatmentLabels } from './utils/fieldRandomizer';
import { calculatePostHoc } from './utils/postHocCalculations';

const INITIAL_CONFIG: DesignConfig = {
  type: 'ral_non_factorial',
  name: 'Rancangan Acak Lengkap (RAL) Non-Faktorial',
  shortName: 'RAL Non-Faktorial',
  description:
    'Digunakan bila media atau kondisi percobaan homogen (misalnya laboratorium, rumah kaca, peternakan terkontrol).',
  t: 5,
  a: 2,
  b: 3,
  r: 4,
  prefixTreatment: 'P',
  startIndexTreatment: 0,
  prefixFactorA: 'A',
  startIndexFactorA: 1,
  prefixFactorB: 'B',
  startIndexFactorB: 1,
  variableName: 'Hasil Gabah Kering',
  unit: 'ton/ha',
  treatmentNames: ['P0 (Kontrol)', 'P1 (Dosis 100 kg)', 'P2 (Dosis 200 kg)', 'P3 (Dosis 300 kg)', 'P4 (Dosis 400 kg)'],
  blockNames: ['Ulangan 1', 'Ulangan 2', 'Ulangan 3', 'Ulangan 4'],
};

const INITIAL_MATRIX = [
  [14.2, 13.8, 14.5, 14.0],
  [18.5, 19.1, 18.0, 18.7],
  [23.4, 24.1, 23.8, 24.5],
  [27.6, 28.2, 27.9, 28.5],
  [26.1, 25.8, 26.5, 26.0],
];

export default function App() {
  const [config, setConfig] = useState<DesignConfig>(INITIAL_CONFIG);
  const [matrix, setMatrix] = useState<number[][]>(INITIAL_MATRIX);
  const [postHocMethod, setPostHocMethod] = useState<PostHocType>('bnt');

  // Sub-sampling configuration
  // For RAL non-factorial, by default single sample per plot (e.g. 1 pot).
  // For RAK, Factorial, and Split Plot, bedengan contains multiple plants (sub-sampling enabled).
  const [numSamplePlants, setNumSamplePlants] = useState<number>(3);
  const [subSamples, setSubSamples] = useState<number[][][]>([]);

  // Active tab state
  const [activeTab, setActiveTab] = useState<
    'fieldmap' | 'subsamples' | 'matrix' | 'steps' | 'anova' | 'posthoc' | 'export'
  >('fieldmap');

  // Treatment customization modal state
  const [isTreatmentModalOpen, setIsTreatmentModalOpen] = useState<boolean>(false);

  // Determine if Sub-Sample tab should be visible
  const isSubSampleTabVisible = config.type !== 'ral_non_factorial';

  // Initialize and synchronize sub-samples matrix
  useEffect(() => {
    const numRows = matrix.length;
    const numCols = matrix[0]?.length || 0;

    setSubSamples((current) => {
      const next: number[][][] = [];
      for (let r = 0; r < numRows; r++) {
        const rowPlots: number[][] = [];
        for (let c = 0; c < numCols; c++) {
          const baseMean = matrix[r]?.[c] || 15.0;
          const existingPlants = current[r]?.[c] || [];
          const plants: number[] = [];
          for (let p = 0; p < numSamplePlants; p++) {
            if (existingPlants[p] !== undefined) {
              plants.push(existingPlants[p]);
            } else {
              // Create realistic individual plant variance around the plot mean
              const offset = (p - (numSamplePlants - 1) / 2) * 0.35;
              plants.push(Number((baseMean + offset).toFixed(2)));
            }
          }
          rowPlots.push(plants);
        }
        next.push(rowPlots);
      }
      return next;
    });
  }, [matrix.length, matrix[0]?.length, numSamplePlants, config.type]);

  // Handle individual sub-sample value edit
  const handleChangeSubSample = (row: number, col: number, plantIdx: number, val: number) => {
    setSubSamples((prev) => {
      const next = prev.map((r) => r.map((c) => [...c]));
      if (next[row]?.[col]) {
        next[row][col][plantIdx] = val;
      }
      return next;
    });
  };

  // Randomize sub-sample plant data with realistic biological variance
  const handleRandomizeSubSamples = () => {
    setSubSamples((prev) => {
      return prev.map((row, rIdx) =>
        row.map((col, cIdx) => {
          const plotMean = matrix[rIdx]?.[cIdx] || 15.0;
          return col.map(() => {
            const noise = (Math.random() - 0.5) * 1.5;
            return Number((plotMean + noise).toFixed(2));
          });
        })
      );
    });
  };

  // Synchronize sub-sample averages into main ANOVA data matrix
  const handleApplyAveragesToMatrix = () => {
    setMatrix((prev) => {
      const next = prev.map((row, rIdx) =>
        row.map((_, cIdx) => {
          const plants = subSamples[rIdx]?.[cIdx] || [];
          if (plants.length === 0) return 0;
          const sum = plants.reduce((a, b) => a + (b || 0), 0);
          return Number((sum / plants.length).toFixed(3));
        })
      );
      return next;
    });
  };

  // Handle configuration update & dimension changes
  const handleConfigChange = (newConfig: Partial<DesignConfig>) => {
    setConfig((prev) => {
      const merged = { ...prev, ...newConfig };

      // Update descriptions & names based on type
      if (newConfig.type && newConfig.type !== prev.type) {
        if (newConfig.type === 'ral_non_factorial') {
          merged.name = 'Rancangan Acak Lengkap (RAL) Non-Faktorial';
          merged.description = 'Percobaan pada kondisi homogen (laboratorium/rumah kaca) dengan satu faktor perlakuan.';
          merged.t = 5;
          merged.r = 4;
          merged.prefixTreatment = 'P';
          merged.startIndexTreatment = 0;
          merged.treatmentNames = ['P0 (Kontrol)', 'P1', 'P2', 'P3', 'P4'];
          merged.blockNames = ['Ulangan 1', 'Ulangan 2', 'Ulangan 3', 'Ulangan 4'];
          if (activeTab === 'subsamples') setActiveTab('matrix');
        } else if (newConfig.type === 'rak_non_factorial') {
          merged.name = 'Rancangan Acak Kelompok (RAK) Non-Faktorial';
          merged.description = 'Percobaan pada media/kondisi heterogen (lapangan dengan gradien kesuburan tanah/lereng).';
          merged.t = 6;
          merged.r = 3;
          merged.prefixTreatment = 'V';
          merged.startIndexTreatment = 1;
          merged.treatmentNames = ['V1', 'V2', 'V3', 'V4', 'V5', 'V6'];
          merged.blockNames = ['Kelompok I', 'Kelompok II', 'Kelompok III'];
        } else if (newConfig.type === 'ral_factorial') {
          merged.name = 'RAL Faktorial (a × b)';
          merged.description = 'Percobaan dengan dua faktor atau lebih pada kondisi homogen.';
          merged.a = 3;
          merged.b = 3;
          merged.r = 3;
          merged.prefixFactorA = 'A';
          merged.startIndexFactorA = 1;
          merged.prefixFactorB = 'B';
          merged.startIndexFactorB = 1;
          merged.factorAName = 'Faktor A';
          merged.factorBName = 'Faktor B';
          merged.blockNames = ['Ulangan 1', 'Ulangan 2', 'Ulangan 3'];
          const generated = generateTreatmentLabels(merged);
          merged.treatmentNames = generated.names;
        } else if (newConfig.type === 'rak_factorial') {
          merged.name = 'RAK Faktorial (a × b)';
          merged.description = 'Percobaan dua faktor pada kondisi heterogen yang dikelompokkan dalam blok kesuburan.';
          merged.a = 3;
          merged.b = 2;
          merged.r = 3;
          merged.prefixFactorA = 'B';
          merged.startIndexFactorA = 1;
          merged.prefixFactorB = 'N';
          merged.startIndexFactorB = 1;
          merged.factorAName = 'Faktor A';
          merged.factorBName = 'Faktor B';
          merged.blockNames = ['Kelompok I', 'Kelompok II', 'Kelompok III'];
          const generated = generateTreatmentLabels(merged);
          merged.treatmentNames = generated.names;
        } else if (newConfig.type === 'split_plot') {
          merged.name = 'Split Plot Design (Petak Terbagi - RAK)';
          merged.description = 'Petak Utama (Main Plot) dan Anak Petak (Subplot) dengan dua galat terpisah (Galat a & Galat b).';
          merged.a = 2;
          merged.b = 3;
          merged.r = 3;
          merged.prefixFactorA = 'A';
          merged.startIndexFactorA = 1;
          merged.prefixFactorB = 'B';
          merged.startIndexFactorB = 1;
          merged.factorAName = 'Petak Utama (A)';
          merged.factorBName = 'Anak Petak (B)';
          merged.blockNames = ['Kelompok I', 'Kelompok II', 'Kelompok III'];
          const generated = generateTreatmentLabels(merged);
          merged.treatmentNames = generated.names;
        }

        // Auto load preset corresponding to new type for instant demo!
        const matchingPreset = PRESETS.find((p) => p.designType === newConfig.type);
        if (matchingPreset) {
          setMatrix(matchingPreset.data);
          merged.variableName = matchingPreset.variableName;
          merged.unit = matchingPreset.unit;
          merged.treatmentNames = matchingPreset.treatmentNames || merged.treatmentNames;
          merged.blockNames = matchingPreset.blockNames || merged.blockNames;
          if (matchingPreset.t) merged.t = matchingPreset.t;
          if (matchingPreset.a) merged.a = matchingPreset.a;
          if (matchingPreset.b) merged.b = matchingPreset.b;
          if (matchingPreset.r) merged.r = matchingPreset.r;
          if (matchingPreset.prefixFactorA) merged.prefixFactorA = matchingPreset.prefixFactorA;
          if (matchingPreset.startIndexFactorA !== undefined) merged.startIndexFactorA = matchingPreset.startIndexFactorA;
          if (matchingPreset.prefixFactorB) merged.prefixFactorB = matchingPreset.prefixFactorB;
          if (matchingPreset.startIndexFactorB !== undefined) merged.startIndexFactorB = matchingPreset.startIndexFactorB;
          if (matchingPreset.prefixTreatment) merged.prefixTreatment = matchingPreset.prefixTreatment;
          if (matchingPreset.startIndexTreatment !== undefined) merged.startIndexTreatment = matchingPreset.startIndexTreatment;
          if (matchingPreset.factorALevelDescriptions) merged.factorALevelDescriptions = matchingPreset.factorALevelDescriptions;
          if (matchingPreset.factorBLevelDescriptions) merged.factorBLevelDescriptions = matchingPreset.factorBLevelDescriptions;
          if (matchingPreset.treatmentLevelDescriptions) merged.treatmentLevelDescriptions = matchingPreset.treatmentLevelDescriptions;
          if (matchingPreset.factorAName) merged.factorAName = matchingPreset.factorAName;
          if (matchingPreset.factorBName) merged.factorBName = matchingPreset.factorBName;
          return merged;
        }
      }

      // If prefix or start index changed, update generated labels cleanly
      if (
        newConfig.prefixTreatment !== undefined ||
        newConfig.startIndexTreatment !== undefined ||
        newConfig.prefixFactorA !== undefined ||
        newConfig.startIndexFactorA !== undefined ||
        newConfig.prefixFactorB !== undefined ||
        newConfig.startIndexFactorB !== undefined
      ) {
        const generated = generateTreatmentLabels(merged, true);
        merged.treatmentNames = generated.names;
      }

      // If dimensions change, adjust matrix size cleanly
      let targetRows = merged.t;
      if (merged.type === 'ral_factorial' || merged.type === 'rak_factorial' || merged.type === 'split_plot') {
        targetRows = (merged.a || 2) * (merged.b || 2);
      }
      const targetCols = merged.r;

      setMatrix((current) => {
        const next: number[][] = [];
        for (let r = 0; r < targetRows; r++) {
          const row: number[] = [];
          for (let c = 0; c < targetCols; c++) {
            row.push(current[r]?.[c] !== undefined ? current[r][c] : 10 + r * 2 + c);
          }
          next.push(row);
        }
        return next;
      });

      return merged;
    });
  };

  // Change individual matrix cell
  const handleChangeCell = (row: number, col: number, val: number) => {
    setMatrix((prev) => {
      const copy = prev.map((r) => [...r]);
      if (copy[row]) {
        copy[row][col] = val;
      }
      return copy;
    });
  };

  // Import data from user Excel/CSV
  const handleImportData = (
    importedMatrix: number[][],
    treatmentNames: string[],
    blockNames: string[]
  ) => {
    setMatrix(importedMatrix);
    setConfig((prev) => ({
      ...prev,
      t: importedMatrix.length,
      r: importedMatrix[0]?.length || prev.r,
      treatmentNames,
      blockNames,
    }));
  };

  // Apply recommended replication r
  const handleApplyRecommendedR = (recommendedR: number) => {
    handleConfigChange({ r: recommendedR });
  };

  // Load Preset
  const handleLoadPreset = () => {
    const preset = PRESETS.find((p) => p.designType === config.type) || PRESETS[0];
    setMatrix(preset.data);
    setConfig((prev) => ({
      ...prev,
      variableName: preset.variableName,
      unit: preset.unit,
      t: preset.t || prev.t,
      a: preset.a || prev.a,
      b: preset.b || prev.b,
      r: preset.r,
      treatmentNames: preset.treatmentNames,
      blockNames: preset.blockNames,
      factorAName: preset.factorAName || prev.factorAName,
      factorBName: preset.factorBName || prev.factorBName,
      prefixFactorA: preset.prefixFactorA || prev.prefixFactorA,
      startIndexFactorA: preset.startIndexFactorA !== undefined ? preset.startIndexFactorA : prev.startIndexFactorA,
      prefixFactorB: preset.prefixFactorB || prev.prefixFactorB,
      startIndexFactorB: preset.startIndexFactorB !== undefined ? preset.startIndexFactorB : prev.startIndexFactorB,
      prefixTreatment: preset.prefixTreatment || prev.prefixTreatment,
      startIndexTreatment: preset.startIndexTreatment !== undefined ? preset.startIndexTreatment : prev.startIndexTreatment,
      factorALevelDescriptions: preset.factorALevelDescriptions || prev.factorALevelDescriptions,
      factorBLevelDescriptions: preset.factorBLevelDescriptions || prev.factorBLevelDescriptions,
      treatmentLevelDescriptions: preset.treatmentLevelDescriptions || prev.treatmentLevelDescriptions,
    }));
  };

  // Randomize realistic data
  const handleRandomizeData = () => {
    setMatrix((prev) => {
      return prev.map((row, rIdx) =>
        row.map((_, cIdx) => {
          const base = 12 + rIdx * 2.8 + cIdx * 0.4;
          const noise = (Math.random() - 0.5) * 1.6;
          return Number((base + noise).toFixed(2));
        })
      );
    });
  };

  // Clear data
  const handleClearData = () => {
    setMatrix((prev) => prev.map((row) => row.map(() => 0)));
  };

  // Add Treatment row
  const handleAddTreatment = () => {
    setMatrix((prev) => {
      const numCols = prev[0]?.length || 3;
      const newRow = new Array(numCols).fill(0);
      return [...prev, newRow];
    });
    setConfig((prev) => {
      const newT = prev.t + 1;
      const prefix = prev.prefixTreatment || 'P';
      const start = prev.startIndexTreatment !== undefined ? prev.startIndexTreatment : 0;
      const newCode = `${prefix}${start + newT - 1}`;
      return {
        ...prev,
        t: newT,
        treatmentNames: [...(prev.treatmentNames || []), newCode],
      };
    });
  };

  // Remove Treatment row
  const handleRemoveTreatment = () => {
    if (matrix.length <= 2) return;
    setMatrix((prev) => prev.slice(0, prev.length - 1));
    setConfig((prev) => ({
      ...prev,
      t: Math.max(2, prev.t - 1),
      treatmentNames: prev.treatmentNames?.slice(0, prev.treatmentNames.length - 1),
    }));
  };

  // Compute ANOVA and Steps
  const { anova, steps } = useMemo(() => {
    return calculateAnova(matrix, config);
  }, [matrix, config]);

  // Compute Post-Hoc Test
  const postHoc = useMemo(() => {
    return calculatePostHoc(matrix, config, anova.ktg, anova.dbg, postHocMethod);
  }, [matrix, config, anova.ktg, anova.dbg, postHocMethod]);

  const handleExportExcel = () => {
    exportToExcel(matrix, config, anova, steps, postHoc);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900">
      <Navbar
        onReset={() => handleConfigChange({ type: config.type })}
        onExportExcel={handleExportExcel}
        designName={config.shortName || config.name}
      />

      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Sidebar Configuration */}
        <Sidebar
          config={config}
          onChangeConfig={handleConfigChange}
          postHocMethod={postHocMethod}
          onChangePostHocMethod={setPostHocMethod}
          onLoadPreset={handleLoadPreset}
          onImportData={handleImportData}
          onApplyRecommendedR={handleApplyRecommendedR}
          onOpenTreatmentModal={() => setIsTreatmentModalOpen(true)}
        />

        {/* Main Content Workspace */}
        <main className="flex-1 p-5 md:p-7 overflow-y-auto max-w-7xl">
          {/* Navigation Tabs */}
          <div className="flex items-center gap-1.5 p-1 bg-white border border-slate-200 rounded-xl mb-6 shadow-2xs overflow-x-auto">
            <button
              onClick={() => setActiveTab('fieldmap')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'fieldmap'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <MapPin className="w-4 h-4" />
              Tab 1: 🗺️ Denah Lapang & Acak
            </button>

            {/* Conditionally rendered Tab 2 for Field Bed Sub-Sampling */}
            {isSubSampleTabVisible && (
              <button
                onClick={() => setActiveTab('subsamples')}
                className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition-all whitespace-nowrap cursor-pointer ${
                  activeTab === 'subsamples'
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <Sprout className="w-4 h-4" />
                Tab 2: 🌿 Data Sub-Sampel Tanaman
              </button>
            )}

            <button
              onClick={() => setActiveTab('matrix')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'matrix'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <Calculator className="w-4 h-4" />
              {isSubSampleTabVisible ? 'Tab 3: 📊 Matriks Rata-rata Plot' : 'Tab 2: 📊 Matriks Data'}
            </button>

            <button
              onClick={() => setActiveTab('steps')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'steps'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              {isSubSampleTabVisible ? 'Tab 4: 📐 Langkah Hitung' : 'Tab 3: 📐 Langkah Hitung'}
            </button>

            <button
              onClick={() => setActiveTab('anova')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'anova'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <FileText className="w-4 h-4" />
              {isSubSampleTabVisible ? 'Tab 5: 📋 Tabel ANOVA' : 'Tab 4: 📋 Tabel ANOVA'}
            </button>

            <button
              onClick={() => setActiveTab('posthoc')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'posthoc'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <ListFilter className="w-4 h-4" />
              {isSubSampleTabVisible ? 'Tab 6: 🔤 Uji Lanjut & Notasi' : 'Tab 5: 🔤 Uji Lanjut & Notasi'}
            </button>

            <button
              onClick={() => setActiveTab('export')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'export'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <Download className="w-4 h-4" />
              {isSubSampleTabVisible ? 'Tab 7: 📥 Export & Skrip Python' : 'Tab 6: 📥 Export & Skrip Python'}
            </button>
          </div>

          {/* Active Tab View */}
          <div className="transition-all duration-200">
            {activeTab === 'fieldmap' && (
              <TabFieldMap
                config={config}
                onNavigateToMatrix={() => setActiveTab(isSubSampleTabVisible ? 'subsamples' : 'matrix')}
              />
            )}

            {activeTab === 'subsamples' && isSubSampleTabVisible && (
              <TabSubSamples
                config={config}
                numSamplePlants={numSamplePlants}
                onChangeNumSamplePlants={setNumSamplePlants}
                subSamples={subSamples}
                onChangeSubSample={handleChangeSubSample}
                onApplyAveragesToMatrix={handleApplyAveragesToMatrix}
                onRandomizeSubSamples={handleRandomizeSubSamples}
              />
            )}

            {activeTab === 'matrix' && (
              <TabMatrix
                matrix={matrix}
                config={config}
                anova={anova}
                onChangeCell={handleChangeCell}
                onImportData={handleImportData}
                onRandomizeData={handleRandomizeData}
                onClearData={handleClearData}
                onAddTreatment={handleAddTreatment}
                onRemoveTreatment={handleRemoveTreatment}
                onOpenTreatmentModal={() => setIsTreatmentModalOpen(true)}
              />
            )}

            {activeTab === 'steps' && <TabSteps steps={steps} />}

            {activeTab === 'anova' && <TabAnova anova={anova} config={config} />}

            {activeTab === 'posthoc' && (
              <TabPostHoc
                postHoc={postHoc}
                config={config}
                onChangeMethod={setPostHocMethod}
              />
            )}

            {activeTab === 'export' && (
              <TabExport
                matrix={matrix}
                config={config}
                anova={anova}
                steps={steps}
                postHoc={postHoc}
              />
            )}
          </div>
        </main>
      </div>

      {/* Modal for Treatment Name & Level Customization */}
      <TreatmentNameModal
        isOpen={isTreatmentModalOpen}
        onClose={() => setIsTreatmentModalOpen(false)}
        config={config}
        onSave={(updated) => handleConfigChange(updated)}
      />
    </div>
  );
}
