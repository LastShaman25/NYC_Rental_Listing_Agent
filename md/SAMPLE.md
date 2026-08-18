<!-- Map & Inventory Command Center -->
<!DOCTYPE html>

<html class="light" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Map &amp; Inventory - NYC Command</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
      tailwind.config = {
        darkMode: "class",
        theme: {
          extend: {
            "colors": {
                    "status-shortlisted": "#3B82F6",
                    "surface-glass": "rgba(255, 255, 255, 0.85)",
                    "secondary": "#006c4a",
                    "surface-container": "#eceef0",
                    "on-error": "#ffffff",
                    "on-tertiary-fixed": "#360f00",
                    "primary-fixed": "#dbe1ff",
                    "surface-variant": "#e0e3e5",
                    "surface": "#f7f9fb",
                    "on-primary": "#ffffff",
                    "surface-dim": "#d8dadc",
                    "secondary-fixed-dim": "#68dba9",
                    "on-tertiary-container": "#ffede6",
                    "on-secondary-fixed-variant": "#005137",
                    "secondary-container": "#82f5c1",
                    "on-surface-variant": "#434655",
                    "inverse-surface": "#2d3133",
                    "status-warning": "#F59E0B",
                    "on-secondary-fixed": "#002114",
                    "on-error-container": "#93000a",
                    "background": "#f7f9fb",
                    "tertiary-container": "#bc4800",
                    "border-subtle": "#E2E8F0",
                    "tertiary-fixed": "#ffdbcd",
                    "primary": "#004ac6",
                    "surface-container-lowest": "#ffffff",
                    "status-occupied": "#64748B",
                    "error": "#ba1a1a",
                    "error-container": "#ffdad6",
                    "on-tertiary-fixed-variant": "#7d2d00",
                    "surface-tint": "#0053db",
                    "surface-container-highest": "#e0e3e5",
                    "surface-bright": "#f7f9fb",
                    "inverse-on-surface": "#eff1f3",
                    "on-tertiary": "#ffffff",
                    "on-surface": "#191c1e",
                    "on-secondary": "#ffffff",
                    "on-primary-fixed": "#00174b",
                    "surface-container-high": "#e6e8ea",
                    "secondary-fixed": "#85f8c4",
                    "primary-fixed-dim": "#b4c5ff",
                    "tertiary-fixed-dim": "#ffb596",
                    "on-secondary-container": "#00714e",
                    "inverse-primary": "#b4c5ff",
                    "on-primary-fixed-variant": "#003ea8",
                    "on-primary-container": "#eeefff",
                    "outline-variant": "#c3c6d7",
                    "tertiary": "#943700",
                    "on-background": "#191c1e",
                    "surface-container-low": "#f2f4f6",
                    "outline": "#737686",
                    "primary-container": "#2563eb"
            },
            "borderRadius": {
                    "DEFAULT": "0.125rem",
                    "lg": "0.25rem",
                    "xl": "0.5rem",
                    "full": "0.75rem"
            },
            "spacing": {
                    "cell-padding": "6px 12px",
                    "panel-margin": "16px",
                    "gutter-dense": "8px",
                    "rail-width": "64px"
            },
            "fontFamily": {
                    "label-caps": [
                            "Inter"
                    ],
                    "display-table": [
                            "Inter"
                    ],
                    "body-compact": [
                            "Inter"
                    ],
                    "headline-panel": [
                            "Inter"
                    ],
                    "marker-id": [
                            "Inter"
                    ]
            },
            "fontSize": {
                    "label-caps": [
                            "11px",
                            {
                                    "lineHeight": "16px",
                                    "letterSpacing": "0.05em",
                                    "fontWeight": "700"
                            }
                    ],
                    "display-table": [
                            "14px",
                            {
                                    "lineHeight": "20px",
                                    "letterSpacing": "-0.01em",
                                    "fontWeight": "600"
                            }
                    ],
                    "body-compact": [
                            "13px",
                            {
                                    "lineHeight": "18px",
                                    "fontWeight": "400"
                            }
                    ],
                    "headline-panel": [
                            "16px",
                            {
                                    "lineHeight": "24px",
                                    "fontWeight": "600"
                            }
                    ],
                    "marker-id": [
                            "10px",
                            {
                                    "lineHeight": "12px",
                                    "fontWeight": "700"
                            }
                    ]
            }
          },
        },
      }
    </script>
<style>
        .custom-scrollbar::-webkit-scrollbar {
            width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
            background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
            background: #E2E8F0;
            border-radius: 4px;
        }
        .map-marker {
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body class="bg-background text-on-background h-screen w-screen overflow-hidden flex flex-col font-body-compact">
<!-- TopNavBar -->
<header class="bg-surface-glass backdrop-blur-md border-b border-border-subtle docked full-width top-0 sticky flex justify-between items-center h-12 px-6 ml-rail-width w-[calc(100%-64px)] z-40">
<div class="flex items-center gap-6">
<h1 class="font-headline-panel text-headline-panel font-black text-on-surface">MetroIntel</h1>
<nav class="flex gap-4">
<a class="text-primary font-bold border-b-2 border-primary pb-1 font-body-compact text-body-compact" href="#">Inventory</a>
<a class="text-on-surface-variant hover:text-primary transition-colors font-body-compact text-body-compact" href="#">Hot-sheets</a>
<a class="text-on-surface-variant hover:text-primary transition-colors font-body-compact text-body-compact" href="#">Reports</a>
</nav>
</div>
<div class="flex items-center gap-4">
<div class="relative hidden lg:block">
<span class="material-symbols-outlined absolute left-2 top-1/2 -translate-y-1/2 text-outline text-[16px]">search</span>
<input class="h-8 pl-8 pr-3 bg-surface-container rounded-DEFAULT border-border-subtle text-body-compact focus:border-primary focus:ring-1 focus:ring-primary w-48" placeholder="Search areas..." type="text"/>
</div>
<div class="flex items-center gap-2">
<button aria-label="refresh" class="opacity-80 hover:opacity-100 transition-opacity p-1 text-on-surface-variant hover:bg-surface-container-high rounded-DEFAULT">
<span class="material-symbols-outlined" data-icon="refresh">refresh</span>
</button>
<button aria-label="cloud_done" class="opacity-80 hover:opacity-100 transition-opacity p-1 text-on-surface-variant hover:bg-surface-container-high rounded-DEFAULT">
<span class="material-symbols-outlined" data-icon="cloud_done">cloud_done</span>
</button>
<button aria-label="notifications" class="opacity-80 hover:opacity-100 transition-opacity p-1 text-on-surface-variant hover:bg-surface-container-high rounded-DEFAULT relative">
<span class="material-symbols-outlined" data-icon="notifications">notifications</span>
<span class="absolute top-1 right-1 w-2 h-2 bg-error rounded-full"></span>
</button>
</div>
<button class="h-8 px-3 text-error border border-error rounded-DEFAULT font-display-table text-display-table hover:bg-error hover:text-on-error transition-colors">Emergency</button>
<button class="h-8 px-3 bg-primary text-on-primary rounded-DEFAULT font-display-table text-display-table hover:bg-primary-container transition-colors">Sync Data</button>
<div class="w-8 h-8 rounded-full bg-surface-container-high border border-border-subtle overflow-hidden">
<img alt="Agent Avatar" class="w-full h-full object-cover" data-alt="A professional headshot of a real estate agent in high-key lighting, modern office background, minimalist aesthetic, sharp focus." src="https://lh3.googleusercontent.com/aida-public/AB6AXuCnzlpzRTHk-a9RxwCCGagW7pHgmn-bmKvR1P6yqPe9NUIq_5BV-gnxk0FEmJkUaNJSqvXoaD11zjsQTnTqv5GqPD3mmvGScF36f32-29WQZ1oB_k8THnhl53IA-XiKtIZ7bKzAa3ffDduUKExylTxNRJ8l9Bx3pyvesudHc3834OEkDZHoYWaaVqMdULRtjPDAGDkrcoVtRJADrs2FYYjU-4TG2H15p07ZAofuUOU39g18ZZ1QYGL-"/>
</div>
</div>
</header>
<!-- Main Content Area with SideNavBar -->
<div class="flex flex-1 overflow-hidden relative">
<!-- SideNavBar -->
<nav class="bg-surface-glass backdrop-blur-xl border-r border-border-subtle fixed left-0 top-0 h-full w-rail-width flex flex-col items-center py-4 z-50">
<div class="mb-8 flex flex-col items-center">
<div class="w-10 h-10 rounded-DEFAULT bg-primary-container flex items-center justify-center text-on-primary-container font-headline-panel text-headline-panel font-bold mb-2">NYC</div>
</div>
<div class="flex flex-col gap-2 w-full px-2">
<a aria-label="Map" class="flex flex-col items-center justify-center p-2 rounded-DEFAULT text-primary border-l-2 border-primary scale-95 active:scale-90 transition-transform bg-surface-container-lowest" href="#">
<span class="material-symbols-outlined" data-icon="map" data-weight="fill" style="font-variation-settings: 'FILL' 1;">map</span>
<span class="font-label-caps text-label-caps mt-1">Map</span>
</a>
<a aria-label="Listings" class="flex flex-col items-center justify-center p-2 rounded-DEFAULT text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined" data-icon="domain">domain</span>
<span class="font-label-caps text-label-caps mt-1">Listings</span>
</a>
<a aria-label="Clients" class="flex flex-col items-center justify-center p-2 rounded-DEFAULT text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined" data-icon="group">group</span>
<span class="font-label-caps text-label-caps mt-1">Clients</span>
</a>
<a aria-label="Operations" class="flex flex-col items-center justify-center p-2 rounded-DEFAULT text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined" data-icon="analytics">analytics</span>
<span class="font-label-caps text-label-caps mt-1">Operations</span>
</a>
</div>
<div class="mt-auto flex flex-col gap-2 w-full px-2 pb-4">
<a aria-label="Settings" class="flex flex-col items-center justify-center p-2 rounded-DEFAULT text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined" data-icon="settings">settings</span>
</a>
<a aria-label="Support" class="flex flex-col items-center justify-center p-2 rounded-DEFAULT text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined" data-icon="help">help</span>
</a>
</div>
</nav>
<!-- Map Canvas (Background) -->
<div class="absolute inset-0 ml-rail-width bg-surface-container-low z-0">
<img alt="Map view of NYC area" class="w-full h-full object-cover opacity-80" data-alt="A highly detailed top-down view of a map of New York City, minimal gray, blue, and white tones. High contrast, professional cartography aesthetic." data-location="New York City" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCrtH2bqd_NDvx0P2ORgtc4BZrOMxsEzQ9E7MXTDk24wMcWKRqMt_YttRwoWjtnxL-MqKGyZrMPSBdqTclrBFNQ3cmp2K7eSErRZpejhJEtusYFQ5jgX0uk7ypooAFAJB5D9oC9l0rThxu-ucarEnux3_jFZXaKwO5WEpE8EILkGU6r-_NMc5jlxuZ-_zo4uyDr5DOYaAjpfEJl_CU6eYdBXbR7jW9YkZlVIUwa4XA8qdqf5f27WQA_"/>
<!-- Floating Map Controls -->
<div class="absolute top-4 left-1/2 -translate-x-1/2 flex gap-2 z-20">
<button class="bg-surface-glass backdrop-blur-md border border-border-subtle rounded-full px-4 py-1.5 font-display-table text-display-table text-primary hover:bg-surface-container-lowest transition-colors shadow-sm flex items-center gap-2">
<span class="material-symbols-outlined text-[18px]">search</span> Search this area
                 </button>
</div>
<!-- Map Markers -->
<!-- Primary Marker -->
<div class="absolute top-1/3 left-1/3 z-10 map-marker flex items-stretch bg-surface-container-lowest border border-border-subtle rounded-DEFAULT overflow-hidden cursor-pointer hover:border-primary transition-colors">
<div class="w-1.5 bg-status-shortlisted"></div>
<div class="px-2 py-1 flex items-center justify-center font-marker-id text-marker-id text-on-surface bg-surface-container-lowest">$3.2k</div>
</div>
<!-- Warning Marker -->
<div class="absolute top-1/4 left-1/2 z-10 map-marker flex items-stretch bg-surface-container-lowest border border-border-subtle rounded-DEFAULT overflow-hidden cursor-pointer hover:border-status-warning transition-colors">
<div class="w-1.5 bg-status-warning"></div>
<div class="px-2 py-1 flex items-center justify-center font-marker-id text-marker-id text-on-surface bg-surface-container-lowest">$4.5k</div>
</div>
<!-- Default Marker -->
<div class="absolute top-1/2 left-2/3 z-10 map-marker flex items-stretch bg-surface-container-lowest border border-border-subtle rounded-DEFAULT overflow-hidden cursor-pointer hover:border-primary transition-colors">
<div class="w-1.5 bg-outline-variant"></div>
<div class="px-2 py-1 flex items-center justify-center font-marker-id text-marker-id text-on-surface bg-surface-container-lowest">$2.8k</div>
</div>
<!-- Map Tools right side -->
<div class="absolute top-4 right-[360px] flex flex-col gap-2 z-20">
<button aria-label="Draw Polygon" class="w-8 h-8 bg-surface-glass backdrop-blur-md border border-border-subtle rounded-DEFAULT flex items-center justify-center text-on-surface-variant hover:text-primary hover:bg-surface-container-lowest transition-colors shadow-sm">
<span class="material-symbols-outlined text-[18px]">polyline</span>
</button>
<button aria-label="Layers" class="w-8 h-8 bg-surface-glass backdrop-blur-md border border-border-subtle rounded-DEFAULT flex items-center justify-center text-on-surface-variant hover:text-primary hover:bg-surface-container-lowest transition-colors shadow-sm">
<span class="material-symbols-outlined text-[18px]">layers</span>
</button>
</div>
</div>
<!-- Left Floating Panel: Filters -->
<div class="absolute left-rail-width top-4 bottom-4 ml-panel-margin w-72 bg-surface-glass backdrop-blur-xl border border-border-subtle rounded-DEFAULT shadow-sm flex flex-col z-20 pointer-events-auto">
<div class="flex items-center justify-between p-3 border-b border-border-subtle">
<h2 class="font-headline-panel text-headline-panel text-on-surface">Filters</h2>
<button class="text-on-surface-variant hover:text-on-surface p-1"><span class="material-symbols-outlined text-[18px]">close</span></button>
</div>
<div class="p-4 flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-6">
<!-- Price Range -->
<div class="flex flex-col gap-2">
<label class="font-label-caps text-label-caps text-on-surface-variant">PRICE RANGE</label>
<div class="flex items-center gap-2">
<input class="w-full h-8 px-2 border border-border-subtle rounded-DEFAULT text-body-compact bg-surface-container-lowest focus:border-primary" placeholder="Min" type="text"/>
<span class="text-outline-variant">-</span>
<input class="w-full h-8 px-2 border border-border-subtle rounded-DEFAULT text-body-compact bg-surface-container-lowest focus:border-primary" placeholder="Max" type="text"/>
</div>
</div>
<!-- Layout -->
<div class="flex flex-col gap-2">
<label class="font-label-caps text-label-caps text-on-surface-variant">LAYOUT</label>
<div class="flex flex-wrap gap-2">
<button class="px-3 py-1 border border-primary bg-primary text-on-primary rounded-DEFAULT font-body-compact text-body-compact">Studio</button>
<button class="px-3 py-1 border border-border-subtle bg-surface-container-lowest text-on-surface rounded-DEFAULT hover:border-primary transition-colors font-body-compact text-body-compact">1BR</button>
<button class="px-3 py-1 border border-border-subtle bg-surface-container-lowest text-on-surface rounded-DEFAULT hover:border-primary transition-colors font-body-compact text-body-compact">2BR</button>
<button class="px-3 py-1 border border-border-subtle bg-surface-container-lowest text-on-surface rounded-DEFAULT hover:border-primary transition-colors font-body-compact text-body-compact">3BR+</button>
</div>
</div>
<!-- Neighborhood -->
<div class="flex flex-col gap-2">
<label class="font-label-caps text-label-caps text-on-surface-variant">NEIGHBORHOOD</label>
<select class="w-full h-8 px-2 border border-border-subtle rounded-DEFAULT text-body-compact bg-surface-container-lowest focus:border-primary">
<option>Manhattan - Downtown</option>
<option>Manhattan - Midtown</option>
<option>Brooklyn - Williamsburg</option>
<option>Jersey City</option>
<option>Hoboken</option>
</select>
</div>
<!-- Laundry -->
<div class="flex flex-col gap-2">
<label class="font-label-caps text-label-caps text-on-surface-variant">LAUNDRY</label>
<div class="flex flex-col gap-1">
<label class="flex items-center gap-2 cursor-pointer">
<input checked="" class="rounded border-border-subtle text-primary focus:ring-primary w-4 h-4" type="checkbox"/>
<span class="font-body-compact text-body-compact text-on-surface">In-unit</span>
</label>
<label class="flex items-center gap-2 cursor-pointer">
<input class="rounded border-border-subtle text-primary focus:ring-primary w-4 h-4" type="checkbox"/>
<span class="font-body-compact text-body-compact text-on-surface">Building</span>
</label>
</div>
</div>
</div>
<div class="p-3 border-t border-border-subtle bg-surface-container-low flex justify-end gap-2">
<button class="px-3 py-1.5 text-on-surface-variant font-display-table text-display-table hover:bg-surface-variant rounded-DEFAULT">Clear</button>
<button class="px-3 py-1.5 bg-primary text-on-primary font-display-table text-display-table rounded-DEFAULT hover:bg-primary-container">Apply</button>
</div>
</div>
<!-- Right Floating Panel: Inventory List -->
<div class="absolute right-0 top-4 bottom-4 mr-panel-margin w-[340px] bg-surface-glass backdrop-blur-xl border border-border-subtle rounded-DEFAULT shadow-sm flex flex-col z-20 pointer-events-auto">
<div class="flex items-center justify-between p-3 border-b border-border-subtle bg-surface-container-lowest rounded-t-DEFAULT">
<div>
<h2 class="font-headline-panel text-headline-panel text-on-surface">Inventory List</h2>
<p class="font-label-caps text-label-caps text-on-surface-variant">24 RESULTS VISIBLE</p>
</div>
<div class="flex gap-1">
<button class="p-1 text-on-surface-variant hover:bg-surface-container-high rounded-DEFAULT"><span class="material-symbols-outlined text-[18px]">sort</span></button>
<button class="p-1 text-on-surface-variant hover:bg-surface-container-high rounded-DEFAULT"><span class="material-symbols-outlined text-[18px]">more_vert</span></button>
</div>
</div>
<div class="flex-1 overflow-y-auto custom-scrollbar p-2 flex flex-col gap-2">
<!-- Property Card 1 -->
<div class="bg-surface-container-lowest border border-border-subtle rounded-DEFAULT p-3 hover:border-primary transition-colors cursor-pointer group">
<div class="flex justify-between items-start mb-2">
<div>
<div class="font-display-table text-display-table text-on-surface">144 W 27th St, #4B</div>
<div class="font-body-compact text-body-compact text-on-surface-variant">Chelsea, Manhattan</div>
</div>
<div class="font-headline-panel text-headline-panel text-primary">$4,200</div>
</div>
<div class="flex gap-3 mb-3">
<span class="font-label-caps text-label-caps text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">1BR</span>
<span class="font-label-caps text-label-caps text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">1BA</span>
<span class="font-label-caps text-label-caps text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">In-Unit W/D</span>
</div>
<div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
<button class="flex-1 h-7 border border-primary text-primary rounded-DEFAULT font-display-table text-[12px] hover:bg-primary hover:text-on-primary transition-colors flex items-center justify-center gap-1">
<span class="material-symbols-outlined text-[14px]">bookmark_add</span> Shortlist
                        </button>
<button class="w-7 h-7 border border-border-subtle text-on-surface-variant rounded-DEFAULT hover:bg-surface-container-high flex items-center justify-center">
<span class="material-symbols-outlined text-[14px]">visibility</span>
</button>
</div>
</div>
<!-- Property Card 2 - Selected -->
<div class="bg-surface-container-lowest border border-status-shortlisted rounded-DEFAULT p-3 hover:border-primary transition-colors cursor-pointer group shadow-[0_0_0_1px_#3B82F6]">
<div class="flex justify-between items-start mb-2">
<div>
<div class="flex items-center gap-1">
<span class="material-symbols-outlined text-status-shortlisted text-[14px]" data-icon="star" data-weight="fill" style="font-variation-settings: 'FILL' 1;">star</span>
<div class="font-display-table text-display-table text-on-surface">100 Christopher St, #2A</div>
</div>
<div class="font-body-compact text-body-compact text-on-surface-variant">West Village, Manhattan</div>
</div>
<div class="font-headline-panel text-headline-panel text-primary">$3,850</div>
</div>
<div class="flex gap-3 mb-3">
<span class="font-label-caps text-label-caps text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">Studio</span>
<span class="font-label-caps text-label-caps text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">1BA</span>
<span class="font-label-caps text-label-caps text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">Bldg W/D</span>
</div>
<div class="flex gap-2">
<button class="flex-1 h-7 bg-primary text-on-primary rounded-DEFAULT font-display-table text-[12px] hover:bg-primary-container transition-colors flex items-center justify-center gap-1">
<span class="material-symbols-outlined text-[14px]">ad_units</span> Select for Ad
                        </button>
</div>
</div>
<!-- Property Card 3 - Warning -->
<div class="bg-surface-container-lowest border border-border-subtle border-l-4 border-l-status-warning rounded-DEFAULT p-3 hover:border-primary transition-colors cursor-pointer group">
<div class="flex justify-between items-start mb-2">
<div>
<div class="font-display-table text-display-table text-on-surface">250 Mercer St, #11F</div>
<div class="font-body-compact text-body-compact text-on-surface-variant">Greenwich Village, Manhattan</div>
</div>
<div class="font-headline-panel text-headline-panel text-primary">$5,100</div>
</div>
<div class="flex gap-3 mb-3">
<span class="font-label-caps text-label-caps text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">2BR</span>
<span class="font-label-caps text-label-caps text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">2BA</span>
</div>
<div class="text-[11px] text-status-warning mb-2 font-display-table flex items-center gap-1">
<span class="material-symbols-outlined text-[12px]">warning</span> Application pending
                    </div>
<div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
<button class="flex-1 h-7 border border-primary text-primary rounded-DEFAULT font-display-table text-[12px] hover:bg-primary hover:text-on-primary transition-colors flex items-center justify-center gap-1">
<span class="material-symbols-outlined text-[14px]">bookmark_add</span> Shortlist
                        </button>
</div>
</div>
</div>
</div>
</div>
</body></html>

<!-- Operational Health Dashboard -->
<!DOCTYPE html>

<html class="light" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Dashboard &amp; Operations - MetroIntel</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    colors: {
                        "status-shortlisted": "#3B82F6",
                        "surface-glass": "rgba(255, 255, 255, 0.85)",
                        "secondary": "#006c4a",
                        "surface-container": "#eceef0",
                        "on-error": "#ffffff",
                        "on-tertiary-fixed": "#360f00",
                        "primary-fixed": "#dbe1ff",
                        "surface-variant": "#e0e3e5",
                        "surface": "#f7f9fb",
                        "on-primary": "#ffffff",
                        "surface-dim": "#d8dadc",
                        "secondary-fixed-dim": "#68dba9",
                        "on-tertiary-container": "#ffede6",
                        "on-secondary-fixed-variant": "#005137",
                        "secondary-container": "#82f5c1",
                        "on-surface-variant": "#434655",
                        "inverse-surface": "#2d3133",
                        "status-warning": "#F59E0B",
                        "on-secondary-fixed": "#002114",
                        "on-error-container": "#93000a",
                        "background": "#f7f9fb",
                        "tertiary-container": "#bc4800",
                        "border-subtle": "#E2E8F0",
                        "tertiary-fixed": "#ffdbcd",
                        "primary": "#004ac6",
                        "surface-container-lowest": "#ffffff",
                        "status-occupied": "#64748B",
                        "error": "#ba1a1a",
                        "error-container": "#ffdad6",
                        "on-tertiary-fixed-variant": "#7d2d00",
                        "surface-tint": "#0053db",
                        "surface-container-highest": "#e0e3e5",
                        "surface-bright": "#f7f9fb",
                        "inverse-on-surface": "#eff1f3",
                        "on-tertiary": "#ffffff",
                        "on-surface": "#191c1e",
                        "on-secondary": "#ffffff",
                        "on-primary-fixed": "#00174b",
                        "surface-container-high": "#e6e8ea",
                        "secondary-fixed": "#85f8c4",
                        "primary-fixed-dim": "#b4c5ff",
                        "tertiary-fixed-dim": "#ffb596",
                        "on-secondary-container": "#00714e",
                        "inverse-primary": "#b4c5ff",
                        "on-primary-fixed-variant": "#003ea8",
                        "on-primary-container": "#eeefff",
                        "outline-variant": "#c3c6d7",
                        "tertiary": "#943700",
                        "on-background": "#191c1e",
                        "surface-container-low": "#f2f4f6",
                        "outline": "#737686",
                        "primary-container": "#2563eb"
                    },
                    borderRadius: {
                        "DEFAULT": "0.125rem",
                        "lg": "0.25rem",
                        "xl": "0.5rem",
                        "full": "0.75rem"
                    },
                    spacing: {
                        "cell-padding": "6px 12px",
                        "panel-margin": "16px",
                        "gutter-dense": "8px",
                        "rail-width": "64px"
                    },
                    fontFamily: {
                        "label-caps": ["Inter"],
                        "display-table": ["Inter"],
                        "body-compact": ["Inter"],
                        "headline-panel": ["Inter"],
                        "marker-id": ["Inter"]
                    },
                    fontSize: {
                        "label-caps": ["11px", { "lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "700" }],
                        "display-table": ["14px", { "lineHeight": "20px", "letterSpacing": "-0.01em", "fontWeight": "600" }],
                        "body-compact": ["13px", { "lineHeight": "18px", "fontWeight": "400" }],
                        "headline-panel": ["16px", { "lineHeight": "24px", "fontWeight": "600" }],
                        "marker-id": ["10px", { "lineHeight": "12px", "fontWeight": "700" }]
                    }
                }
            }
        }
    </script>
<style>.map-bg {
    background-image: url(https://lh3.googleusercontent.com/aida-public/AB6AXuCbGPp6PIkUzd72hURE5J6jukZkTifcmgCgjYrLcewOo4XJK_8wHeHB-ZH1J04cza6c3zIQi3hHh3NkjdlMxbhVNt42oqDmtPySehtFkJAZUQlNBNClubyEDcLvtbw7tpdP6Cpk5q95wvZJSv-QhGh-WIyKf0zOB8mK5e0TBVA8Vdq2h6M19Q3FHsBnaWu3RG3VQmrMAPS-TaQRPtASJ_pGSoEaoaPnMjMjvYmnA2DoDL0z-8USiQWD);
    background-size: cover;
    background-position: center
    }
.glass-panel {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid #E2E8F0
    }
.chart-grid {
    background-image: linear-gradient(to right, #E2E8F0 1px, transparent 1px), linear-gradient(to bottom, #E2E8F0 1px, transparent 1px);
    background-size: 20px 20px;
    opacity: 0.5
    }</style>
</head>
<body class="bg-background text-on-surface h-screen overflow-hidden flex font-body-compact">
<!-- Base Map Layer -->
<div class="absolute inset-0 z-0 map-bg" data-alt="A highly detailed, desaturated, high-contrast street map of New York City and New Jersey, viewed from directly above. The map focuses on major rental zones, using a clean, modern cartographic style. Rivers and bodies of water are a crisp, light gray, while landmasses are bright white. Street grids are depicted with extremely fine, subtle silver lines. The overall aesthetic is professional, technical, and optimized to serve as an unobtrusive background for a high-stakes real estate dashboard. Light mode." data-location="New York City" style="background-image: url('https://lh3.googleusercontent.com/aida-public/AB6AXuBVqVsyekqGddibr1t3SNFkSukDKFkTMQ0_U0qqnLcBW7q-XxnaHfA3ElAUAipkoglVhA9WsOXgcmh-XgM5Mk_lOMac1PHLqMxbrF2nHpylUbs1vXGJP8lhaAi32ITqDHakaEaSVbqMchCwL75K2oXqzIBniHcs0Bw3nJMfoBjedvbWwDL46-XOji3b0H_apVsrimwx8aN8IHUdZd5KHI8lvVpL4QQt-Mc7qCyB-0oTK94_Bh9RJLuL')"></div>
<div class="absolute inset-0 z-0 bg-surface/40 backdrop-blur-sm pointer-events-none"></div>
<!-- SideNavBar -->
<nav class="fixed left-0 top-0 h-full w-rail-width bg-surface-glass backdrop-blur-xl border-r border-border-subtle flex flex-col items-center py-4 z-50 transition-all">
<!-- Header / Logo -->
<div class="mb-8 flex flex-col items-center">
<span class="font-headline-panel text-headline-panel font-bold text-primary mb-1">MI</span>
<img alt="Agent Profile" class="w-8 h-8 rounded-full border border-border-subtle object-cover mt-4" data-alt="A small, professional headshot of an active, focused real estate agent. Bright, clear lighting against a neutral light gray background. High-resolution, professional portrait. Minimalist style fitting a modern software interface." src="https://lh3.googleusercontent.com/aida-public/AB6AXuAMUKeXK_CO5338EJBdcYO-DPYgVIFglfQhh1a5mMeNDXX0r7imm_bLbypRp7deuGUr4cfRy__1ZRIbbhXL5SK2sNoJxRzLVrxZMbx8xqcvasFx5FjPUYyOETSoJrb56wnJb9HR603erX5i6FG4z4IT8MNgU_z1CkmLiMXetGjLdgIPig7Ico2OgiFtkvCxpivradEWryWtxT0WWPcDspCnOePfbwX8n8dIHBLBTBNS2BL409Hvvjk-"/>
</div>
<!-- Main Tabs -->
<div class="flex-1 flex flex-col gap-6 w-full items-center mt-4">
<!-- Map (Inactive) -->
<button class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90 relative group">
<span class="material-symbols-outlined text-2xl mb-1 group-hover:text-primary transition-colors">map</span>
<span class="font-label-caps text-label-caps">Map</span>
</button>
<!-- Listings (Inactive) -->
<button class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90 relative group">
<span class="material-symbols-outlined text-2xl mb-1 group-hover:text-primary transition-colors">domain</span>
<span class="font-label-caps text-label-caps">Listings</span>
</button>
<!-- Clients (Inactive) -->
<button class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90 relative group">
<span class="material-symbols-outlined text-2xl mb-1 group-hover:text-primary transition-colors">group</span>
<span class="font-label-caps text-label-caps">Clients</span>
</button>
<!-- Operations (Active - Dashboard intent maps closely to Operations) -->
<button class="flex flex-col items-center justify-center w-full py-2 text-primary border-l-2 border-primary hover:bg-surface-container-high transition-colors scale-95 active:scale-90 relative group bg-surface-container-lowest">
<span class="material-symbols-outlined text-2xl mb-1" style="font-variation-settings: 'FILL' 1;">analytics</span>
<span class="font-label-caps text-label-caps">Operations</span>
</button>
</div>
<!-- Footer Tabs -->
<div class="flex flex-col gap-4 w-full items-center mt-auto mb-4 border-t border-border-subtle pt-4">
<button class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90">
<span class="material-symbols-outlined text-2xl mb-1">settings</span>
<span class="font-label-caps text-label-caps text-[9px]">Settings</span>
</button>
<button class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant hover:bg-surface-container-high transition-colors scale-95 active:scale-90">
<span class="material-symbols-outlined text-2xl mb-1">help</span>
<span class="font-label-caps text-label-caps text-[9px]">Support</span>
</button>
</div>
</nav>
<!-- Main Content Area -->
<div class="ml-rail-width flex-1 flex flex-col h-full w-[calc(100%-64px)] relative z-10">
<!-- TopNavBar -->
<header class="flex justify-between items-center h-12 px-6 bg-surface-glass backdrop-blur-md border-b border-border-subtle sticky top-0 z-40">
<!-- Left: Brand & Links -->
<div class="flex items-center gap-8 h-full">
<span class="font-headline-panel text-headline-panel font-black text-on-surface">MetroIntel</span>
<nav class="hidden md:flex h-full gap-6">
<!-- Nav links derived from JSON -->
<button class="h-full flex items-center font-body-compact text-body-compact text-on-surface-variant hover:text-primary transition-colors border-b-2 border-transparent hover:border-border-subtle">
                        Inventory
                    </button>
<button class="h-full flex items-center font-body-compact text-body-compact text-on-surface-variant hover:text-primary transition-colors border-b-2 border-transparent hover:border-border-subtle">
                        Hot-sheets
                    </button>
<button class="h-full flex items-center font-body-compact text-body-compact text-on-surface-variant hover:text-primary transition-colors border-b-2 border-transparent hover:border-border-subtle">
                        Reports
                    </button>
</nav>
</div>
<!-- Right: Actions -->
<div class="flex items-center gap-4">
<!-- Trailing Primary Action -->
<button class="px-3 py-1.5 bg-primary text-on-primary font-display-table text-display-table rounded-DEFAULT hover:bg-primary/90 transition-colors flex items-center gap-2">
<span class="material-symbols-outlined text-sm">sync</span>
                    Sync Data
                </button>
<!-- Trailing Secondary Action -->
<button class="px-3 py-1.5 bg-error/10 text-error font-display-table text-display-table rounded-DEFAULT hover:bg-error/20 transition-colors border border-error/20">
                    Emergency
                </button>
<!-- Icon Actions -->
<div class="flex items-center gap-2 ml-2 border-l border-border-subtle pl-4">
<button class="p-1.5 text-on-surface-variant hover:text-primary transition-colors opacity-80 hover:opacity-100 rounded-DEFAULT hover:bg-surface-container">
<span class="material-symbols-outlined">refresh</span>
</button>
<button class="p-1.5 text-on-surface-variant hover:text-primary transition-colors opacity-80 hover:opacity-100 rounded-DEFAULT hover:bg-surface-container">
<span class="material-symbols-outlined">cloud_done</span>
</button>
<button class="p-1.5 text-on-surface-variant hover:text-primary transition-colors opacity-80 hover:opacity-100 rounded-DEFAULT hover:bg-surface-container relative">
<span class="material-symbols-outlined">notifications</span>
<span class="absolute top-1 right-1 w-2 h-2 bg-status-shortlisted rounded-full"></span>
</button>
</div>
</div>
</header>
<!-- Dashboard Canvas -->
<main class="flex-1 overflow-y-auto p-panel-margin pb-24">
<!-- Header Section -->
<div class="flex justify-between items-end mb-6">
<div>
<h1 class="font-headline-panel text-[24px] leading-tight font-bold text-on-surface mb-1">NYC Command Center</h1>
<p class="text-on-surface-variant font-body-compact">Real-time portfolio operations and system health.</p>
</div>
<div class="flex gap-2">
<span class="px-2 py-1 bg-secondary-container/30 text-secondary-container font-label-caps text-label-caps rounded-DEFAULT border border-secondary-container/50 flex items-center gap-1">
<span class="w-1.5 h-1.5 bg-secondary rounded-full animate-pulse"></span>
                        System Nominal
                    </span>
<span class="px-2 py-1 bg-surface-container text-on-surface-variant font-label-caps text-label-caps rounded-DEFAULT border border-border-subtle">
                        Last Refresh: 10s ago
                    </span>
</div>
</div>
<!-- Bento Grid Layout -->
<div class="grid grid-cols-12 gap-gutter-dense auto-rows-[minmax(120px,auto)]">
<!-- KPI: Total Active -->
<div class="col-span-12 md:col-span-4 glass-panel rounded-lg p-4 flex flex-col justify-between">
<div class="flex justify-between items-start">
<span class="font-label-caps text-label-caps text-on-surface-variant">Total Active Listings</span>
<span class="material-symbols-outlined text-primary text-xl">real_estate_agent</span>
</div>
<div class="mt-4">
<div class="font-headline-panel text-[32px] font-black leading-none text-on-surface">14,285</div>
<div class="flex items-center gap-1 mt-2 font-body-compact text-[11px] text-secondary">
<span class="material-symbols-outlined text-[14px]">trending_up</span>
<span>+4.2% from last week</span>
</div>
</div>
</div>
<!-- KPI: New Today -->
<div class="col-span-12 md:col-span-4 glass-panel rounded-lg p-4 flex flex-col justify-between">
<div class="flex justify-between items-start">
<span class="font-label-caps text-label-caps text-on-surface-variant">New Inventory Today</span>
<span class="material-symbols-outlined text-status-shortlisted text-xl">fiber_new</span>
</div>
<div class="mt-4">
<div class="font-headline-panel text-[32px] font-black leading-none text-on-surface">412</div>
<div class="flex items-center gap-1 mt-2 font-body-compact text-[11px] text-on-surface-variant">
<span>Mostly in Brooklyn Heights</span>
</div>
</div>
</div>
<!-- KPI: Warnings -->
<div class="col-span-12 md:col-span-4 glass-panel rounded-lg p-4 flex flex-col justify-between border-l-4 border-l-status-warning">
<div class="flex justify-between items-start">
<span class="font-label-caps text-label-caps text-on-surface-variant">Data Anomalies</span>
<span class="material-symbols-outlined text-status-warning text-xl">warning</span>
</div>
<div class="mt-4">
<div class="font-headline-panel text-[32px] font-black leading-none text-on-surface">18</div>
<div class="flex items-center gap-1 mt-2 font-body-compact text-[11px] text-status-warning">
<span class="material-symbols-outlined text-[14px]">sync_problem</span>
<span>Requires manual review</span>
</div>
</div>
</div>
<!-- Chart: Inventory Freshness -->
<div class="col-span-12 md:col-span-8 glass-panel rounded-lg p-4 row-span-2 flex flex-col">
<div class="flex justify-between items-center mb-4 border-b border-border-subtle pb-2">
<h2 class="font-display-table text-display-table text-on-surface flex items-center gap-2">
<span class="material-symbols-outlined text-sm">bar_chart</span>
                            Inventory Freshness
                        </h2>
<button class="text-primary font-label-caps text-label-caps hover:underline">View Full Report</button>
</div>
<div class="flex-1 relative w-full h-full min-h-[200px]">
<!-- Simulated Chart Background Grid -->
<div class="absolute inset-0 chart-grid z-0"></div>
<!-- Simulated Chart Bars -->
<div class="absolute inset-0 z-10 flex items-end justify-between px-4 pb-6 pt-4">
<!-- Bar 1: 0-7 Days -->
<div class="w-[12%] h-[80%] bg-primary/20 border border-primary/50 rounded-t-sm relative group">
<div class="absolute -top-6 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-inverse-surface text-inverse-on-surface text-[10px] px-2 py-1 rounded-DEFAULT whitespace-nowrap z-20">4,520 listings</div>
</div>
<!-- Bar 2: 8-14 Days -->
<div class="w-[12%] h-[65%] bg-primary/20 border border-primary/50 rounded-t-sm relative group">
<div class="absolute -top-6 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-inverse-surface text-inverse-on-surface text-[10px] px-2 py-1 rounded-DEFAULT whitespace-nowrap z-20">3,100 listings</div>
</div>
<!-- Bar 3: 15-30 Days -->
<div class="w-[12%] h-[40%] bg-status-occupied/20 border border-status-occupied/50 rounded-t-sm relative group"></div>
<!-- Bar 4: 31-60 Days -->
<div class="w-[12%] h-[25%] bg-status-occupied/20 border border-status-occupied/50 rounded-t-sm relative group"></div>
<!-- Bar 5: 60+ Days -->
<div class="w-[12%] h-[15%] bg-status-warning/20 border border-status-warning/50 rounded-t-sm relative group"></div>
</div>
<!-- X Axis Labels -->
<div class="absolute bottom-0 w-full flex justify-between px-4 text-[10px] text-on-surface-variant font-body-compact">
<div class="w-[12%] text-center">0-7d</div>
<div class="w-[12%] text-center">8-14d</div>
<div class="w-[12%] text-center">15-30d</div>
<div class="w-[12%] text-center">31-60d</div>
<div class="w-[12%] text-center">60d+</div>
</div>
</div>
</div>
<!-- Sync Status Feed -->
<div class="col-span-12 md:col-span-4 glass-panel rounded-lg p-0 row-span-3 flex flex-col overflow-hidden">
<div class="p-4 border-b border-border-subtle bg-surface-container-lowest/50">
<h2 class="font-display-table text-display-table text-on-surface flex items-center gap-2">
<span class="material-symbols-outlined text-sm">wifi_tethering</span>
                            Sync Status Feed
                        </h2>
</div>
<div class="flex-1 overflow-y-auto p-4 space-y-4">
<!-- Feed Item 1 -->
<div class="flex gap-3 items-start border-b border-border-subtle pb-3 last:border-0">
<div class="w-6 h-6 rounded-full bg-secondary-container flex items-center justify-center shrink-0 mt-0.5">
<span class="material-symbols-outlined text-[12px] text-secondary">check</span>
</div>
<div>
<div class="font-body-compact text-[12px] font-semibold text-on-surface">Streeteasy Scraper completed</div>
<div class="font-body-compact text-[11px] text-on-surface-variant mt-0.5">Parsed 1,204 records. 45 new.</div>
<div class="font-label-caps text-[9px] text-outline mt-1 uppercase">2 mins ago</div>
</div>
</div>
<!-- Feed Item 2 -->
<div class="flex gap-3 items-start border-b border-border-subtle pb-3 last:border-0">
<div class="w-6 h-6 rounded-full bg-status-warning/20 flex items-center justify-center shrink-0 mt-0.5 border border-status-warning/30">
<span class="material-symbols-outlined text-[12px] text-status-warning">error_outline</span>
</div>
<div>
<div class="font-body-compact text-[12px] font-semibold text-on-surface">NJMLS Connect Retry</div>
<div class="font-body-compact text-[11px] text-on-surface-variant mt-0.5">Connection timed out. Retrying (2/3)...</div>
<div class="font-label-caps text-[9px] text-outline mt-1 uppercase">12 mins ago</div>
</div>
</div>
<!-- Feed Item 3 -->
<div class="flex gap-3 items-start border-b border-border-subtle pb-3 last:border-0">
<div class="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5 border border-primary/20">
<span class="material-symbols-outlined text-[12px] text-primary">data_object</span>
</div>
<div>
<div class="font-body-compact text-[12px] font-semibold text-on-surface">Price Reduction Batch Processed</div>
<div class="font-body-compact text-[11px] text-on-surface-variant mt-0.5">Applied to 89 listings in Manhattan.</div>
<div class="font-label-caps text-[9px] text-outline mt-1 uppercase">45 mins ago</div>
</div>
</div>
<!-- Feed Item 4 -->
<div class="flex gap-3 items-start border-b border-border-subtle pb-3 last:border-0">
<div class="w-6 h-6 rounded-full bg-secondary-container flex items-center justify-center shrink-0 mt-0.5">
<span class="material-symbols-outlined text-[12px] text-secondary">check</span>
</div>
<div>
<div class="font-body-compact text-[12px] font-semibold text-on-surface">Nightly Backup OK</div>
<div class="font-body-compact text-[11px] text-on-surface-variant mt-0.5">S3 storage sync successful.</div>
<div class="font-label-caps text-[9px] text-outline mt-1 uppercase">5 hours ago</div>
</div>
</div>
</div>
</div>
<!-- Map: Market Coverage Heatmap -->
<div class="col-span-12 md:col-span-8 glass-panel rounded-lg p-0 row-span-2 flex flex-col overflow-hidden relative">
<div class="absolute top-0 left-0 w-full p-4 border-b border-border-subtle/50 bg-surface-glass backdrop-blur-md z-20 flex justify-between items-center">
<h2 class="font-display-table text-display-table text-on-surface flex items-center gap-2">
<span class="material-symbols-outlined text-sm">my_location</span>
                            Market Coverage
                        </h2>
<div class="flex gap-2">
<button class="px-2 py-1 bg-surface-container text-on-surface-variant font-label-caps text-[9px] rounded-DEFAULT border border-border-subtle hover:bg-surface-variant">NYC</button>
<button class="px-2 py-1 bg-transparent text-on-surface-variant font-label-caps text-[9px] rounded-DEFAULT border border-transparent hover:bg-surface-container">NJ</button>
</div>
</div>
<!-- Inner Map Canvas area (simulated heatmap) -->
<div class="flex-1 w-full bg-surface-container-low relative" data-alt="A focused, stylized map snippet showing the Hudson River dividing Manhattan and New Jersey. The map is in a clean, light-mode style with pale gray land and white water. There are subtle, abstract, glowing blue 'heatmap' blobs concentrated over Midtown Manhattan and Jersey City, indicating data density. The aesthetic is modern, tech-focused, and suitable for a data dashboard." data-location="Hudson River Map Area" style="background-image: url('https://lh3.googleusercontent.com/aida-public/AB6AXuCmpNbSjiQnhsP_Bxaa17q5_mW02ZkHkuYIgEPnIWxcvIXmeD2N3i7bG_Fxf_QaMuFjHzDujn2y6Scz2hqUgrT2PZzrscjOfj2F_Cf9bCCf5l_qdjMiiMLUrwSt0ouvGwBWJXYIWHU1lzHx9DJkzd7NxfqeXg_3-9oUsMTLlnJUoVuA-Rfl9FgJWBy04W526HojzGReELR3NG4lVN1RxMa6JEz1wQD1Jz1xehLq0Cz5yhHN7t0KOfOT')">
<!-- Heatmap Overlay Simulation -->
<div class="absolute inset-0 bg-gradient-to-tr from-transparent via-primary/10 to-transparent pointer-events-none mix-blend-multiply"></div>
<!-- Map Markers (Simulated density nodes) -->
<div class="absolute top-[40%] left-[60%] w-12 h-12 bg-primary/30 rounded-full blur-md"></div>
<div class="absolute top-[45%] left-[58%] w-6 h-6 bg-primary/60 rounded-full blur-sm"></div>
<div class="absolute top-[60%] left-[30%] w-16 h-16 bg-status-shortlisted/20 rounded-full blur-md"></div>
<div class="absolute top-[20%] left-[70%] w-8 h-8 bg-status-warning/40 rounded-full blur-md"></div>
<!-- Data Density Legend -->
<div class="absolute bottom-4 right-4 bg-surface-glass backdrop-blur-md p-2 rounded-DEFAULT border border-border-subtle shadow-sm flex items-center gap-2">
<span class="font-label-caps text-[9px] text-on-surface-variant">Density</span>
<div class="w-16 h-2 rounded-full bg-gradient-to-r from-surface-container to-primary"></div>
</div>
</div>
</div>
<!-- System Health Panel -->
<div class="col-span-12 glass-panel rounded-lg p-4 flex items-center justify-between overflow-x-auto">
<div class="flex items-center gap-6 whitespace-nowrap pr-4">
<div class="flex flex-col">
<span class="font-label-caps text-[10px] text-on-surface-variant">API Gateway</span>
<div class="flex items-center gap-1 mt-1">
<span class="w-2 h-2 bg-secondary rounded-full"></span>
<span class="font-body-compact text-[12px] font-semibold text-on-surface">99.9% Uptime</span>
</div>
</div>
<div class="w-px h-8 bg-border-subtle"></div>
<div class="flex flex-col">
<span class="font-label-caps text-[10px] text-on-surface-variant">Database Latency</span>
<div class="flex items-center gap-1 mt-1">
<span class="w-2 h-2 bg-secondary rounded-full"></span>
<span class="font-body-compact text-[12px] font-semibold text-on-surface">24ms (Avg)</span>
</div>
</div>
<div class="w-px h-8 bg-border-subtle"></div>
<div class="flex flex-col">
<span class="font-label-caps text-[10px] text-on-surface-variant">Image Processing Queue</span>
<div class="flex items-center gap-1 mt-1">
<span class="w-2 h-2 bg-status-warning rounded-full animate-pulse"></span>
<span class="font-body-compact text-[12px] font-semibold text-on-surface">142 items pending</span>
</div>
</div>
</div>
<button class="shrink-0 px-3 py-1.5 bg-surface-container-high text-on-surface font-label-caps text-[10px] rounded-DEFAULT border border-border-subtle hover:bg-surface-variant transition-colors flex items-center gap-1">
<span class="material-symbols-outlined text-[14px]">tune</span>
                        System Config
                    </button>
</div>
</div>
</main>
</div>
</body></html>

<!-- Client Shortlists & Comparison -->
<!DOCTYPE html>

<html lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>NYC Command - Client Shortlists</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    "colors": {
                        "status-shortlisted": "#3B82F6",
                        "surface-glass": "rgba(255, 255, 255, 0.85)",
                        "secondary": "#006c4a",
                        "surface-container": "#eceef0",
                        "on-error": "#ffffff",
                        "on-tertiary-fixed": "#360f00",
                        "primary-fixed": "#dbe1ff",
                        "surface-variant": "#e0e3e5",
                        "surface": "#f7f9fb",
                        "on-primary": "#ffffff",
                        "surface-dim": "#d8dadc",
                        "secondary-fixed-dim": "#68dba9",
                        "on-tertiary-container": "#ffede6",
                        "on-secondary-fixed-variant": "#005137",
                        "secondary-container": "#82f5c1",
                        "on-surface-variant": "#434655",
                        "inverse-surface": "#2d3133",
                        "status-warning": "#F59E0B",
                        "on-secondary-fixed": "#002114",
                        "on-error-container": "#93000a",
                        "background": "#f7f9fb",
                        "tertiary-container": "#bc4800",
                        "border-subtle": "#E2E8F0",
                        "tertiary-fixed": "#ffdbcd",
                        "primary": "#004ac6",
                        "surface-container-lowest": "#ffffff",
                        "status-occupied": "#64748B",
                        "error": "#ba1a1a",
                        "error-container": "#ffdad6",
                        "on-tertiary-fixed-variant": "#7d2d00",
                        "surface-tint": "#0053db",
                        "surface-container-highest": "#e0e3e5",
                        "surface-bright": "#f7f9fb",
                        "inverse-on-surface": "#eff1f3",
                        "on-tertiary": "#ffffff",
                        "on-surface": "#191c1e",
                        "on-secondary": "#ffffff",
                        "on-primary-fixed": "#00174b",
                        "surface-container-high": "#e6e8ea",
                        "secondary-fixed": "#85f8c4",
                        "primary-fixed-dim": "#b4c5ff",
                        "tertiary-fixed-dim": "#ffb596",
                        "on-secondary-container": "#00714e",
                        "inverse-primary": "#b4c5ff",
                        "on-primary-fixed-variant": "#003ea8",
                        "on-primary-container": "#eeefff",
                        "outline-variant": "#c3c6d7",
                        "tertiary": "#943700",
                        "on-background": "#191c1e",
                        "surface-container-low": "#f2f4f6",
                        "outline": "#737686",
                        "primary-container": "#2563eb"
                    },
                    "borderRadius": {
                        "DEFAULT": "0.125rem",
                        "lg": "0.25rem",
                        "xl": "0.5rem",
                        "full": "0.75rem"
                    },
                    "spacing": {
                        "cell-padding": "6px 12px",
                        "panel-margin": "16px",
                        "gutter-dense": "8px",
                        "rail-width": "64px"
                    },
                    "fontFamily": {
                        "label-caps": ["Inter"],
                        "display-table": ["Inter"],
                        "body-compact": ["Inter"],
                        "headline-panel": ["Inter"],
                        "marker-id": ["Inter"]
                    },
                    "fontSize": {
                        "label-caps": ["11px", { "lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "700" }],
                        "display-table": ["14px", { "lineHeight": "20px", "letterSpacing": "-0.01em", "fontWeight": "600" }],
                        "body-compact": ["13px", { "lineHeight": "18px", "fontWeight": "400" }],
                        "headline-panel": ["16px", { "lineHeight": "24px", "fontWeight": "600" }],
                        "marker-id": ["10px", { "lineHeight": "12px", "fontWeight": "700" }]
                    }
                }
            }
        }
    </script>
<style>.glass-panel {
    background-color: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(12px);
    border: 1px solid #E2E8F0
    }
.map-bg {
    background-image: url(https://lh3.googleusercontent.com/aida-public/AB6AXuDwcosDk_rxVXAuV3zZTpOMmspEhAiiLMtforzAMdTI1P9bFLdq6zx4xA6HQTuD0E8jsgOu80ZDNzwDX1ikMxIyvdOZm8U1SmlDjUCBesOuRg2Hcxma1BDWi5fkP4ovosky1XQjccwY-0l9HylneGdeadeEO7-wBTYHhJyqlls8o0Yw8u5aLDeZZIX54KlaYMmSYeYVkSVKkZKydxJcyUw450qpNmfjh41XhKuCY4jYOWjetqRoLqNN);
    background-size: cover;
    background-position: center
    }
.table-row-hover:hover {
    background-color: #f2f4f6
    }</style>
</head>
<body class="bg-background text-on-background font-body-compact text-body-compact overflow-hidden antialiased flex h-screen">
<!-- Global Map Canvas (Base Layer) -->
<div class="fixed inset-0 w-full h-full z-0 map-bg" data-alt="A highly detailed, professional map view of New York City and New Jersey. The map uses a minimalist, modern light-mode style with subtle grays and whites for landmasses, and pale blues for water. Thin, precise lines delineate streets and transit routes. The overall aesthetic is analytical, clean, and suited for high-stakes operational real estate software." data-location="New York City" style=""></div>
<!-- SideNavBar (from JSON) -->
<nav class="fixed left-0 top-0 h-full w-rail-width bg-surface-glass dark:bg-surface-glass font-label-caps text-label-caps backdrop-blur-xl border-r border-border-subtle flex flex-col items-center py-4 z-50">
<div class="mb-8 flex flex-col items-center group cursor-pointer opacity-80 hover:opacity-100 transition-opacity">
<img alt="Agent Profile" class="w-10 h-10 rounded-full border-2 border-primary object-cover mb-2" data-alt="A small, professional headshot avatar of a real estate agent. The agent looks confident and sharp, set against a clean, neutral gray background. The lighting is bright and professional, emphasizing a modern corporate aesthetic." src="https://lh3.googleusercontent.com/aida-public/AB6AXuB9w0YBCvAPrVCW3tFQOvCr3NfFGlNH4h2_uG9Hk1y7vXgobqionNTgBbV6TKlrZe6Weee6R6-2cDCpirRCTSkvWEZA6PwK52cSGCS1jwTYhClbb63XxzVLIyYcCwsr9kyXNC5xMxK8t_UsuazACovIuqcuwm6GOciil0qsICuwhAfz-Z6JZolmxkezMIV7NWRuG48hpsvZbyPCzXWlU14gfBKf4O7Nz6qqAsaPeA8D3Tl6HB23AyLI"/>
</div>
<div class="flex-1 flex flex-col gap-6 w-full">
<a class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant dark:text-outline-variant hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined mb-1">map</span>
<span>Map</span>
</a>
<a class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant dark:text-outline-variant hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined mb-1">domain</span>
<span>Listings</span>
</a>
<a class="flex flex-col items-center justify-center w-full py-2 text-primary dark:text-primary-fixed border-l-2 border-primary hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform bg-primary/5" href="#">
<span class="material-symbols-outlined mb-1" style="font-variation-settings: 'FILL' 1;">group</span>
<span>Clients</span>
</a>
<a class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant dark:text-outline-variant hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined mb-1">analytics</span>
<span>Operations</span>
</a>
</div>
<div class="flex flex-col gap-4 w-full mt-auto">
<a class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant dark:text-outline-variant hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined mb-1">settings</span>
<span>Settings</span>
</a>
<a class="flex flex-col items-center justify-center w-full py-2 text-on-surface-variant dark:text-outline-variant hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform" href="#">
<span class="material-symbols-outlined mb-1">help</span>
<span>Support</span>
</a>
</div>
</nav>
<!-- TopNavBar (from JSON) -->
<header class="flex justify-between items-center h-12 px-6 ml-rail-width w-[calc(100%-64px)] z-40 bg-surface-glass dark:bg-surface-glass font-body-compact text-body-compact backdrop-blur-md border-b border-border-subtle docked full-width top-0 sticky">
<div class="flex items-center gap-6">
<div class="font-headline-panel text-headline-panel font-black text-on-surface dark:text-on-background tracking-tight">MetroIntel</div>
<nav class="hidden md:flex gap-4">
<a class="text-on-surface-variant dark:text-outline-variant hover:text-primary dark:hover:text-primary-fixed transition-colors opacity-80 hover:opacity-100 transition-opacity" href="#">Inventory</a>
<a class="text-on-surface-variant dark:text-outline-variant hover:text-primary dark:hover:text-primary-fixed transition-colors opacity-80 hover:opacity-100 transition-opacity" href="#">Hot-sheets</a>
<a class="text-on-surface-variant dark:text-outline-variant hover:text-primary dark:hover:text-primary-fixed transition-colors opacity-80 hover:opacity-100 transition-opacity" href="#">Reports</a>
</nav>
</div>
<div class="flex items-center gap-4">
<div class="flex items-center bg-surface-container border border-border-subtle rounded px-2 py-1">
<span class="material-symbols-outlined text-outline text-sm mr-2">search</span>
<input class="bg-transparent border-none text-body-compact focus:ring-0 p-0 w-48 text-on-surface-variant" placeholder="Search..." type="text"/>
</div>
<div class="flex items-center gap-2 text-on-surface-variant">
<button class="hover:text-primary transition-colors"><span class="material-symbols-outlined">refresh</span></button>
<button class="hover:text-primary transition-colors"><span class="material-symbols-outlined">cloud_done</span></button>
<button class="hover:text-primary transition-colors"><span class="material-symbols-outlined">notifications</span></button>
</div>
<div class="flex gap-2">
<button class="bg-surface-container text-on-surface px-3 py-1 rounded border border-border-subtle hover:bg-surface-variant transition-colors font-display-table text-display-table">Emergency</button>
<button class="bg-primary text-on-primary px-3 py-1 rounded hover:bg-primary-container transition-colors font-display-table text-display-table">Sync Data</button>
</div>
</div>
</header>
<!-- Main Content Canvas -->
<main class="ml-rail-width w-[calc(100%-64px)] h-[calc(100vh-48px)] flex z-10 relative mt-12 p-panel-margin gap-panel-margin">
<!-- Client List Panel (Left Sidebar) -->
<aside class="w-80 glass-panel rounded-lg flex flex-col h-full shadow-sm flex-shrink-0">
<div class="p-gutter-dense border-b border-border-subtle flex justify-between items-center bg-surface-container-lowest/50 rounded-t-lg">
<h2 class="font-headline-panel text-headline-panel text-on-surface">Active Clients</h2>
<button class="text-primary hover:text-primary-container"><span class="material-symbols-outlined text-sm">add</span></button>
</div>
<div class="p-gutter-dense">
<div class="relative">
<span class="material-symbols-outlined absolute left-2 top-1.5 text-outline text-sm">search</span>
<input class="w-full h-8 pl-8 pr-2 border border-border-subtle rounded bg-surface-container-lowest text-body-compact focus:ring-1 focus:ring-primary focus:border-primary" placeholder="Filter clients..." type="text"/>
</div>
</div>
<div class="flex-1 overflow-y-auto p-gutter-dense space-y-1">
<!-- Client Items -->
<div class="p-2 rounded bg-primary/10 border border-primary/20 cursor-pointer flex justify-between items-center group">
<div>
<div class="font-display-table text-display-table text-on-surface">John Doe</div>
<div class="text-label-caps font-label-caps text-on-surface-variant mt-0.5">1BR • Jersey City • $3.5k</div>
</div>
<span class="w-2 h-2 rounded-full bg-status-shortlisted"></span>
</div>
<div class="p-2 rounded hover:bg-surface-container-low border border-transparent cursor-pointer flex justify-between items-center transition-colors">
<div>
<div class="font-display-table text-display-table text-on-surface">Sarah Smith</div>
<div class="text-label-caps font-label-caps text-on-surface-variant mt-0.5">Studio • West Village • $4.2k</div>
</div>
<span class="w-2 h-2 rounded-full bg-status-warning"></span>
</div>
<div class="p-2 rounded hover:bg-surface-container-low border border-transparent cursor-pointer flex justify-between items-center transition-colors">
<div>
<div class="font-display-table text-display-table text-on-surface">Michael Chen</div>
<div class="text-label-caps font-label-caps text-on-surface-variant mt-0.5">2BR • Hoboken • $4.8k</div>
</div>
<span class="w-2 h-2 rounded-full bg-surface-dim"></span>
</div>
<div class="p-2 rounded hover:bg-surface-container-low border border-transparent cursor-pointer flex justify-between items-center transition-colors">
<div>
<div class="font-display-table text-display-table text-on-surface">Emily Davis</div>
<div class="text-label-caps font-label-caps text-on-surface-variant mt-0.5">1BR • Williamsburg • $3.9k</div>
</div>
<span class="w-2 h-2 rounded-full bg-surface-dim"></span>
</div>
</div>
</aside>
<!-- Main Workspace -->
<section class="flex-1 flex flex-col gap-panel-margin h-full min-w-0">
<!-- Top: Active Filters & Map Context -->
<div class="glass-panel rounded-lg p-gutter-dense flex flex-col gap-2 shrink-0">
<div class="flex justify-between items-start">
<div>
<h1 class="font-headline-panel text-headline-panel text-on-surface flex items-center gap-2">
                            John Doe <span class="text-on-surface-variant font-normal text-sm">| 1BR JC Search</span>
</h1>
<div class="flex gap-2 mt-2 flex-wrap">
<span class="px-2 py-1 rounded bg-surface-container border border-border-subtle text-label-caps font-label-caps text-on-surface flex items-center gap-1">
<span class="material-symbols-outlined text-[12px]">monetization_on</span> Max $3,500
                            </span>
<span class="px-2 py-1 rounded bg-surface-container border border-border-subtle text-label-caps font-label-caps text-on-surface flex items-center gap-1">
<span class="material-symbols-outlined text-[12px]">train</span> &lt; 30m WTC
                            </span>
<span class="px-2 py-1 rounded bg-primary/10 border border-primary/30 text-primary text-label-caps font-label-caps flex items-center gap-1">
<span class="material-symbols-outlined text-[12px]">pets</span> Pet Friendly
                            </span>
<span class="px-2 py-1 rounded bg-surface-container border border-border-subtle text-label-caps font-label-caps text-on-surface flex items-center gap-1">
<span class="material-symbols-outlined text-[12px]">directions_walk</span> In-Unit W/D
                            </span>
</div>
</div>
<div class="flex gap-2">
<button class="bg-surface-container text-on-surface px-3 py-1.5 rounded border border-border-subtle hover:bg-surface-variant transition-colors flex items-center gap-1">
<span class="material-symbols-outlined text-sm">edit</span> Edit Criteria
                        </button>
</div>
</div>
</div>
<!-- Middle: Shortlist Comparison Grid -->
<div class="glass-panel rounded-lg flex flex-col flex-1 min-h-0">
<div class="p-gutter-dense border-b border-border-subtle flex justify-between items-center bg-surface-container-lowest/50 rounded-t-lg">
<h2 class="font-headline-panel text-headline-panel text-on-surface">Shortlisted Properties</h2>
<div class="flex gap-2">
<button class="text-on-surface-variant hover:text-primary transition-colors" title="Export PDF"><span class="material-symbols-outlined">picture_as_pdf</span></button>
<button class="text-on-surface-variant hover:text-primary transition-colors" title="Share Link"><span class="material-symbols-outlined">share</span></button>
</div>
</div>
<div class="flex-1 overflow-auto">
<table class="w-full text-left border-collapse">
<thead class="sticky top-0 bg-surface-container-low border-b border-border-subtle font-label-caps text-label-caps text-on-surface-variant z-10">
<tr>
<th class="p-cell-padding font-normal">Property</th>
<th class="p-cell-padding font-normal w-24">Price</th>
<th class="p-cell-padding font-normal w-20">SqFt</th>
<th class="p-cell-padding font-normal w-24">Transit (WTC)</th>
<th class="p-cell-padding font-normal w-24">Status</th>
<th class="p-cell-padding font-normal w-12 text-center">Action</th>
</tr>
</thead>
<tbody class="font-body-compact text-body-compact text-on-surface">
<tr class="border-b border-border-subtle table-row-hover">
<td class="p-cell-padding">
<div class="font-display-table text-display-table">The Morgan</div>
<div class="text-outline text-xs">160 Morgan St, Unit 4B</div>
</td>
<td class="p-cell-padding">$3,400</td>
<td class="p-cell-padding">750</td>
<td class="p-cell-padding flex items-center gap-1 text-secondary"><span class="material-symbols-outlined text-[14px]">subway</span> 15m</td>
<td class="p-cell-padding"><span class="px-1.5 py-0.5 bg-status-shortlisted/10 text-status-shortlisted border border-status-shortlisted/20 rounded text-[10px] uppercase font-bold tracking-wider">Shortlisted</span></td>
<td class="p-cell-padding text-center">
<button class="text-outline hover:text-primary"><span class="material-symbols-outlined text-sm">queue</span></button>
</td>
</tr>
<tr class="border-b border-border-subtle table-row-hover bg-surface-container-lowest/30">
<td class="p-cell-padding">
<div class="font-display-table text-display-table">Haus25</div>
<div class="text-outline text-xs">25 Christopher Columbus Dr, Unit 12C</div>
</td>
<td class="p-cell-padding">$3,550 <span class="text-error text-xs ml-1" title="Over budget">↑</span></td>
<td class="p-cell-padding">785</td>
<td class="p-cell-padding flex items-center gap-1 text-secondary"><span class="material-symbols-outlined text-[14px]">subway</span> 12m</td>
<td class="p-cell-padding"><span class="px-1.5 py-0.5 bg-status-warning/10 text-status-warning border border-status-warning/20 rounded text-[10px] uppercase font-bold tracking-wider">Viewing</span></td>
<td class="p-cell-padding text-center">
<button class="text-outline hover:text-primary"><span class="material-symbols-outlined text-sm">queue</span></button>
</td>
</tr>
<tr class="border-b border-border-subtle table-row-hover">
<td class="p-cell-padding">
<div class="font-display-table text-display-table">VyV</div>
<div class="text-outline text-xs">474 Warren St, Unit 8A</div>
</td>
<td class="p-cell-padding">$3,200</td>
<td class="p-cell-padding">710</td>
<td class="p-cell-padding flex items-center gap-1 text-on-surface-variant"><span class="material-symbols-outlined text-[14px]">subway</span> 22m</td>
<td class="p-cell-padding"><span class="px-1.5 py-0.5 bg-surface-container-high text-on-surface-variant border border-border-subtle rounded text-[10px] uppercase font-bold tracking-wider">Match</span></td>
<td class="p-cell-padding text-center">
<button class="text-primary hover:text-primary-container"><span class="material-symbols-outlined text-sm">library_add_check</span></button>
</td>
</tr>
<tr class="border-b border-border-subtle table-row-hover bg-surface-container-lowest/30">
<td class="p-cell-padding">
<div class="font-display-table text-display-table">Urby</div>
<div class="text-outline text-xs">200 Greene St, Unit 22F</div>
</td>
<td class="p-cell-padding">$3,450</td>
<td class="p-cell-padding">690</td>
<td class="p-cell-padding flex items-center gap-1 text-secondary"><span class="material-symbols-outlined text-[14px]">subway</span> 18m</td>
<td class="p-cell-padding"><span class="px-1.5 py-0.5 bg-surface-container-high text-on-surface-variant border border-border-subtle rounded text-[10px] uppercase font-bold tracking-wider">Match</span></td>
<td class="p-cell-padding text-center">
<button class="text-outline hover:text-primary"><span class="material-symbols-outlined text-sm">queue</span></button>
</td>
</tr>
</tbody>
</table>
</div>
</div>
<!-- Bottom: Ad/Send Queue -->
<div class="glass-panel rounded-lg h-32 shrink-0 flex flex-col">
<div class="p-2 border-b border-border-subtle bg-surface-container-lowest/50 rounded-t-lg flex justify-between items-center">
<h3 class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Queue for Client</h3>
<button class="bg-primary text-on-primary px-3 py-1 rounded hover:bg-primary-container transition-colors text-xs font-bold flex items-center gap-1">
<span class="material-symbols-outlined text-[14px]">send</span> Dispatch Itinerary
                    </button>
</div>
<div class="flex-1 p-2 flex gap-2 overflow-x-auto items-center">
<!-- Queued Item -->
<div class="border border-primary bg-primary/5 rounded p-2 flex items-center gap-3 min-w-[200px]">
<div class="w-10 h-10 bg-surface-container-high rounded flex items-center justify-center text-outline">
<span class="material-symbols-outlined">apartment</span>
</div>
<div class="flex-1 min-w-0">
<div class="text-sm font-bold truncate">The Morgan</div>
<div class="text-xs text-outline truncate">160 Morgan St, 4B</div>
</div>
<button class="text-outline hover:text-error"><span class="material-symbols-outlined text-sm">close</span></button>
</div>
<!-- Empty State Placeholder -->
<div class="border border-dashed border-border-subtle rounded p-2 flex items-center justify-center gap-2 min-w-[200px] h-[58px] text-outline text-xs">
<span class="material-symbols-outlined text-sm">add_circle</span> Add to queue
                    </div>
</div>
</div>
</section>
</main>
</body></html>

<!-- Apartment Detail & Transit Analysis -->
<!DOCTYPE html>

<html lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Listing Detail - MetroIntel</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    "colors": {
                        "status-shortlisted": "#3B82F6",
                        "surface-glass": "rgba(255, 255, 255, 0.85)",
                        "secondary": "#006c4a",
                        "surface-container": "#eceef0",
                        "on-error": "#ffffff",
                        "on-tertiary-fixed": "#360f00",
                        "primary-fixed": "#dbe1ff",
                        "surface-variant": "#e0e3e5",
                        "surface": "#f7f9fb",
                        "on-primary": "#ffffff",
                        "surface-dim": "#d8dadc",
                        "secondary-fixed-dim": "#68dba9",
                        "on-tertiary-container": "#ffede6",
                        "on-secondary-fixed-variant": "#005137",
                        "secondary-container": "#82f5c1",
                        "on-surface-variant": "#434655",
                        "inverse-surface": "#2d3133",
                        "status-warning": "#F59E0B",
                        "on-secondary-fixed": "#002114",
                        "on-error-container": "#93000a",
                        "background": "#f7f9fb",
                        "tertiary-container": "#bc4800",
                        "border-subtle": "#E2E8F0",
                        "tertiary-fixed": "#ffdbcd",
                        "primary": "#004ac6",
                        "surface-container-lowest": "#ffffff",
                        "status-occupied": "#64748B",
                        "error": "#ba1a1a",
                        "error-container": "#ffdad6",
                        "on-tertiary-fixed-variant": "#7d2d00",
                        "surface-tint": "#0053db",
                        "surface-container-highest": "#e0e3e5",
                        "surface-bright": "#f7f9fb",
                        "inverse-on-surface": "#eff1f3",
                        "on-tertiary": "#ffffff",
                        "on-surface": "#191c1e",
                        "on-secondary": "#ffffff",
                        "on-primary-fixed": "#00174b",
                        "surface-container-high": "#e6e8ea",
                        "secondary-fixed": "#85f8c4",
                        "primary-fixed-dim": "#b4c5ff",
                        "tertiary-fixed-dim": "#ffb596",
                        "on-secondary-container": "#00714e",
                        "inverse-primary": "#b4c5ff",
                        "on-primary-fixed-variant": "#003ea8",
                        "on-primary-container": "#eeefff",
                        "outline-variant": "#c3c6d7",
                        "tertiary": "#943700",
                        "on-background": "#191c1e",
                        "surface-container-low": "#f2f4f6",
                        "outline": "#737686",
                        "primary-container": "#2563eb"
                    },
                    "borderRadius": {
                        "DEFAULT": "0.125rem",
                        "lg": "0.25rem",
                        "xl": "0.5rem",
                        "full": "0.75rem"
                    },
                    "spacing": {
                        "cell-padding": "6px 12px",
                        "panel-margin": "16px",
                        "gutter-dense": "8px",
                        "rail-width": "64px"
                    },
                    "fontFamily": {
                        "label-caps": ["Inter"],
                        "display-table": ["Inter"],
                        "body-compact": ["Inter"],
                        "headline-panel": ["Inter"],
                        "marker-id": ["Inter"]
                    },
                    "fontSize": {
                        "label-caps": ["11px", { "lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "700" }],
                        "display-table": ["14px", { "lineHeight": "20px", "letterSpacing": "-0.01em", "fontWeight": "600" }],
                        "body-compact": ["13px", { "lineHeight": "18px", "fontWeight": "400" }],
                        "headline-panel": ["16px", { "lineHeight": "24px", "fontWeight": "600" }],
                        "marker-id": ["10px", { "lineHeight": "12px", "fontWeight": "700" }]
                    }
                }
            }
        }
    </script>
</head>
<body class="bg-background text-on-background font-body-compact text-body-compact min-h-screen relative overflow-hidden flex">
<!-- Base Map Layer -->
<div class="fixed inset-0 z-0">
<img alt="Base Map" class="w-full h-full object-cover opacity-80" data-alt="A highly detailed, ultra-high resolution aerial map view of downtown Manhattan and New Jersey shorelines. The map is rendered in a modern, light-mode, minimalist aesthetic with desaturated greys and soft whites, featuring crisp geometric lines for streets and subtle topography. Deep blues represent the Hudson River, adding a calm, professional tone suitable for an enterprise application interface." data-location="New York City" src="https://lh3.googleusercontent.com/aida-public/AB6AXuDieJfXO9ZzNx8S7UFFBYyw-nfZuxEtY_TEKbeQa5_pPiOfocxv8cOHSBxpCrzmNoBVjwQXrEf605YGn-iDbC3E2sodE9TLPxsuow31AJTui5Jr0k1YCpOZ7vHUS6srDSU_UNlNyQTbzAAz3D1qcUK7Dj-xd7DdE4iKM_fYUxzCrygxaMLONjlsThEaokYayrTSkhRAHznUpI9liaFC-B1AfFU-F7ixzYSilFPsIj3E-6mVIOJGt6co"/>
</div>
<!-- SideNavBar -->
<nav class="bg-surface-glass dark:bg-surface-glass fixed left-0 top-0 h-full w-rail-width backdrop-blur-xl border-r border-border-subtle flex flex-col items-center py-4 z-50">
<div class="mb-8">
<span class="material-symbols-outlined text-primary dark:text-primary-fixed" style="font-size: 32px;">apartment</span>
</div>
<div class="flex-1 flex flex-col gap-6 w-full">
<a class="flex flex-col items-center justify-center w-full py-2 hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform text-on-surface-variant dark:text-outline-variant group" href="#">
<span class="material-symbols-outlined mb-1 group-hover:text-primary dark:group-hover:text-primary-fixed transition-colors">map</span>
<span class="font-label-caps text-label-caps">Map</span>
</a>
<a class="flex flex-col items-center justify-center w-full py-2 hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform text-primary dark:text-primary-fixed border-l-2 border-primary group" href="#">
<span class="material-symbols-outlined mb-1" style="font-variation-settings: 'FILL' 1;">domain</span>
<span class="font-label-caps text-label-caps">Listings</span>
</a>
<a class="flex flex-col items-center justify-center w-full py-2 hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform text-on-surface-variant dark:text-outline-variant group" href="#">
<span class="material-symbols-outlined mb-1 group-hover:text-primary dark:group-hover:text-primary-fixed transition-colors">group</span>
<span class="font-label-caps text-label-caps">Clients</span>
</a>
<a class="flex flex-col items-center justify-center w-full py-2 hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform text-on-surface-variant dark:text-outline-variant group" href="#">
<span class="material-symbols-outlined mb-1 group-hover:text-primary dark:group-hover:text-primary-fixed transition-colors">analytics</span>
<span class="font-label-caps text-label-caps">Operations</span>
</a>
</div>
<div class="mt-auto flex flex-col gap-6 w-full">
<a class="flex flex-col items-center justify-center w-full py-2 hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform text-on-surface-variant dark:text-outline-variant group" href="#">
<span class="material-symbols-outlined mb-1 group-hover:text-primary dark:group-hover:text-primary-fixed transition-colors">settings</span>
<span class="font-label-caps text-label-caps">Settings</span>
</a>
<a class="flex flex-col items-center justify-center w-full py-2 hover:bg-surface-container-high dark:hover:bg-surface-container-highest transition-colors scale-95 active:scale-90 transition-transform text-on-surface-variant dark:text-outline-variant group" href="#">
<span class="material-symbols-outlined mb-1 group-hover:text-primary dark:group-hover:text-primary-fixed transition-colors">help</span>
<span class="font-label-caps text-label-caps">Support</span>
</a>
<div class="mt-4 flex flex-col items-center">
<img alt="Agent Profile" class="w-8 h-8 rounded-full object-cover border border-border-subtle" data-alt="A high-quality, professional headshot of a real estate agent in a modern corporate setting. The lighting is soft and flattering, creating a polished, approachable look. The background is a slightly blurred modern office space, fitting a sophisticated, enterprise application light-mode aesthetic." src="https://lh3.googleusercontent.com/aida-public/AB6AXuDSaPodFbKyzBBBFisIzCOeQgCZUCK2u4zZdE63xS_B6oB4DATWf4nosQgH87ATu2ybamubY42nAaOj0iQ3DVquFzetnkPeG9oGXvBpKGIXJmt9sBctTVnqyyxd9DjuYMZmEm6xtib7J099ch7nPTZy3kGdslACO2C40jgs5sUc1ndY0Cmoa67YhHRthHIaffC9M3dYrjOvQlcL79wJ3aljIKNmPFRPs0euWMiDafq1xwVqmlZI5WFr"/>
</div>
</div>
</nav>
<!-- Main Content Area -->
<div class="flex-1 ml-rail-width flex flex-col h-screen overflow-hidden relative z-10">
<!-- TopNavBar -->
<header class="bg-surface-glass dark:bg-surface-glass backdrop-blur-md border-b border-border-subtle flex justify-between items-center h-12 px-6 z-40">
<div class="flex items-center gap-6">
<span class="font-headline-panel text-headline-panel font-black text-on-surface dark:text-on-background">MetroIntel</span>
<!-- Search -->
<div class="relative w-64 ml-4">
<span class="material-symbols-outlined absolute left-2 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm">search</span>
<input class="w-full h-8 pl-8 pr-3 bg-surface-container-lowest border border-border-subtle rounded focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all text-xs" placeholder="Search NYC/NJ properties..." type="text"/>
</div>
</div>
<nav class="flex items-center gap-6 hidden md:flex">
<a class="text-primary dark:text-primary-fixed font-bold border-b-2 border-primary pb-1 h-12 flex items-center" href="#">Inventory</a>
<a class="text-on-surface-variant dark:text-outline-variant hover:text-primary dark:hover:text-primary-fixed transition-colors opacity-80 hover:opacity-100 h-12 flex items-center" href="#">Hot-sheets</a>
<a class="text-on-surface-variant dark:text-outline-variant hover:text-primary dark:hover:text-primary-fixed transition-colors opacity-80 hover:opacity-100 h-12 flex items-center" href="#">Reports</a>
</nav>
<div class="flex items-center gap-4">
<div class="flex items-center gap-2 text-on-surface-variant">
<button class="opacity-80 hover:opacity-100 transition-opacity p-1 hover:bg-surface-container rounded"><span class="material-symbols-outlined text-sm">refresh</span></button>
<button class="opacity-80 hover:opacity-100 transition-opacity p-1 hover:bg-surface-container rounded"><span class="material-symbols-outlined text-sm">cloud_done</span></button>
<button class="opacity-80 hover:opacity-100 transition-opacity p-1 hover:bg-surface-container rounded relative">
<span class="material-symbols-outlined text-sm">notifications</span>
<span class="absolute top-1 right-1 w-2 h-2 bg-error rounded-full border border-surface-glass"></span>
</button>
</div>
<div class="h-6 w-px bg-border-subtle"></div>
<button class="text-xs font-semibold text-error hover:bg-error-container hover:text-on-error-container px-3 py-1 rounded transition-colors border border-error">Emergency</button>
<button class="text-xs font-semibold bg-primary text-on-primary px-3 py-1 rounded hover:bg-primary-container transition-colors shadow-sm">Sync Data</button>
<img alt="Agent Avatar" class="w-7 h-7 rounded-full object-cover border border-border-subtle ml-2" data-alt="A small, circular avatar image of a female professional in a sharp blazer, suitable for a light-mode enterprise UI. The background is a plain, soft grey to maintain focus." src="https://lh3.googleusercontent.com/aida-public/AB6AXuCk9fKOOuoAYI4GU5ppoN19DTggi5UASY4DDOsnw_8ZHhMt-pR8efcDtGV3LsMUjhelTSUDSrf2ZSe7S0Cl0Stv99KVlx7yP2y93lcr_toiS4m1AfKQMRg90e1saR5xQGAwfP6zNFbuxTWGQWYV49wbqd5h-42WxMPywoQY2-eJZ8bR9rAyAvlv9ZLM_Q4zPEa2atvY8dWbYaxr6L3_Bx0elEC0mdmjlDN8aR0JenmF-kZD-sYMcgeX"/>
</div>
</header>
<!-- Listing Detail Canvas -->
<main class="flex-1 overflow-y-auto p-panel-margin pb-20 flex gap-panel-margin custom-scrollbar">
<!-- Left Column: Details & Gallery -->
<div class="w-7/12 flex flex-col gap-panel-margin">
<!-- Hero Gallery Grid -->
<div class="bg-surface-glass backdrop-blur-xl border border-border-subtle rounded-xl p-2 shadow-sm flex flex-col gap-2">
<!-- Main Image -->
<div class="w-full h-64 rounded-lg overflow-hidden relative group cursor-pointer">
<img alt="Primary Property View" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" data-alt="A wide-angle, high-end real estate photograph of a luxury living room in a high-rise NYC apartment. The room features floor-to-ceiling windows with a panoramic view of the Manhattan skyline at golden hour. The interior design is modern, with sleek lines, light oak flooring, and minimal, chic furniture. The lighting is bright and natural, fitting a premium, light-mode enterprise application aesthetic." src="https://lh3.googleusercontent.com/aida-public/AB6AXuCdRNF4-GZqmJRpNAHDgHqUUa6FCcKpGSts2QeGb1NkUpxqOA4GsCGKsd96jl5qCy0cU5FBSw570Q7Fw1a6K0rEjg5TbSnTm0VNLd045bDv8dvtcIRdXN7xmjBl19IUpUtRLDRESIVMFBYjD_ZrN19KlA8Yjp_X3cIGV5MvVuU8oMQG5tQjE6qxNZxJYrFnysVtroMNQlO5jx-i8Wc_-OOhk2Apn4IS1ss3pumMnliWfHPxuE9T19L2"/>
<div class="absolute top-3 left-3 bg-status-shortlisted text-on-primary px-2 py-1 rounded font-label-caps text-label-caps flex items-center gap-1 shadow-md">
<span class="material-symbols-outlined" style="font-size: 12px;">verified</span> Verified
                        </div>
<div class="absolute bottom-3 right-3 bg-inverse-surface/80 text-inverse-on-surface backdrop-blur-md px-3 py-1.5 rounded font-label-caps text-label-caps flex items-center gap-1">
<span class="material-symbols-outlined" style="font-size: 14px;">photo_library</span> 1/24
                        </div>
</div>
<!-- Thumbnails -->
<div class="flex gap-2 h-20">
<div class="flex-1 rounded-lg overflow-hidden cursor-pointer opacity-90 hover:opacity-100 transition-opacity border border-border-subtle">
<img alt="Kitchen" class="w-full h-full object-cover" data-alt="A bright, modern kitchen in a luxury apartment. Features white marble countertops, stainless steel appliances, and minimalist white cabinetry. Natural light pours in from a window off-screen. High-end real estate photography style, matching a light-mode UI." src="https://lh3.googleusercontent.com/aida-public/AB6AXuBfSJIyMs2jo30IQUj-Ni2Q6EDeBLJiKGp8TXKr5kVYTSey_Q1ArWf1ehG-xF-KMC6Lz77pGN9ZTCbg1A32z-7V2DlvP_cctT-rQ-P7JDAn74ENhAUoDkje-yNSr6c4WbBpSKTArTDAnp1Fw4eyPRIMAOlGZztAR1aArXGCbnZq3wzls7P9RH6y9dZc10ffqDscPsBz3k785a5MPCprekOtSbcNxOAUAgg069OIabbqmjitDa2Sb5ks"/>
</div>
<div class="flex-1 rounded-lg overflow-hidden cursor-pointer opacity-90 hover:opacity-100 transition-opacity border border-border-subtle">
<img alt="Bedroom" class="w-full h-full object-cover" data-alt="A spacious bedroom in a high-rise apartment with large windows overlooking the city. A neatly made king-size bed with white linens and subtle grey accents. The lighting is soft and natural, emphasizing a calm, professional aesthetic." src="https://lh3.googleusercontent.com/aida-public/AB6AXuDUU4sNcvQvM9wZT_r-33g1Zmw5ObLrUu5-owgimPhed1q7p3c4eJchT38WsyBRxWgC-Wimos6qU9Ehf1nelZrDEX4yEf7oKm3e4Kyusqn8H8XchF2LUFPM1BjSjH-ZstZRNK-fv-_VlPYvb2iaaQp_eno3-qebqXnboPCaPgt3nhlSgHzbfHGbI8ASdI4nb6QSFMEWXL21ERVzQ0z-W4qCxJaZtbt1RGZFUSU5GTeK6gUKCHaPtfQo"/>
</div>
<div class="flex-1 rounded-lg overflow-hidden cursor-pointer opacity-90 hover:opacity-100 transition-opacity border border-border-subtle relative">
<img alt="Bathroom" class="w-full h-full object-cover" data-alt="A sleek, modern bathroom featuring a glass-enclosed walk-in shower, large grey tiles, and a floating vanity. Bright, clinical lighting suitable for a high-quality real estate listing, integrating well with a light-mode enterprise interface." src="https://lh3.googleusercontent.com/aida-public/AB6AXuCr34TqzRZ1ipZyJ-DYA40kSdn_6eOLeXZNBvrAyLluQjJZkldoAy83QwCoUrzKROHoBlqe0sZx7-aNnf-F8Z56CUKuZqnO5djAchhzsQwu3CxbvddqQ8pb9JuVNSPZmaSzEi20ZFlkW8bt1-bcDSTHZvSvO1cimFnMa4ElDeTVcNFdBHlt89n-fLUL6J3Ljl7tO5zA1qaC7a_Tb5W9oRCjrSonDq2kXSzFgcz8wzPW-TlRyNcDQ8nk"/>
<div class="absolute inset-0 bg-inverse-surface/60 flex items-center justify-center rounded-lg">
<span class="font-display-table text-display-table text-on-primary">+21</span>
</div>
</div>
</div>
</div>
<!-- Overview Data Panel -->
<div class="bg-surface-glass backdrop-blur-xl border border-border-subtle rounded-xl p-4 shadow-sm">
<div class="flex justify-between items-start mb-4 border-b border-border-subtle pb-4">
<div>
<h1 class="font-headline-panel text-2xl font-bold text-on-surface tracking-tight">450 Washington St, Apt 12B</h1>
<p class="text-on-surface-variant mt-1 flex items-center gap-2">
<span class="material-symbols-outlined text-sm">location_on</span> Tribeca, Manhattan, NY 10013
                            </p>
</div>
<div class="text-right">
<div class="font-headline-panel text-3xl font-black text-primary tracking-tight">$8,500<span class="text-lg text-on-surface-variant font-normal">/mo</span></div>
<div class="flex items-center justify-end gap-2 mt-1">
<span class="bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-label-caps text-label-caps border border-secondary">No Fee</span>
<span class="text-status-occupied font-label-caps text-label-caps border border-border-subtle px-2 py-0.5 rounded">Avail. Sept 1</span>
</div>
</div>
</div>
<!-- Key Metrics Grid -->
<div class="grid grid-cols-4 gap-4 mb-6">
<div class="bg-surface-container-low p-3 rounded-lg border border-border-subtle text-center">
<span class="material-symbols-outlined text-on-surface-variant mb-1" style="font-size: 20px;">bed</span>
<div class="font-display-table text-display-table text-on-surface">2 Beds</div>
</div>
<div class="bg-surface-container-low p-3 rounded-lg border border-border-subtle text-center">
<span class="material-symbols-outlined text-on-surface-variant mb-1" style="font-size: 20px;">shower</span>
<div class="font-display-table text-display-table text-on-surface">2.5 Baths</div>
</div>
<div class="bg-surface-container-low p-3 rounded-lg border border-border-subtle text-center">
<span class="material-symbols-outlined text-on-surface-variant mb-1" style="font-size: 20px;">straighten</span>
<div class="font-display-table text-display-table text-on-surface">1,250 sqft</div>
</div>
<div class="bg-surface-container-low p-3 rounded-lg border border-border-subtle text-center">
<span class="material-symbols-outlined text-on-surface-variant mb-1" style="font-size: 20px;">floor</span>
<div class="font-display-table text-display-table text-on-surface">12th Floor</div>
</div>
</div>
<!-- Features -->
<div class="mb-4">
<h3 class="font-label-caps text-label-caps text-on-surface-variant mb-2">AMENITIES &amp; FEATURES</h3>
<div class="flex flex-wrap gap-2">
<span class="px-2 py-1 bg-surface border border-border-subtle rounded text-xs text-on-surface flex items-center gap-1 hover:border-primary transition-colors cursor-default"><span class="material-symbols-outlined text-[14px]">local_laundry_service</span> In-Unit W/D</span>
<span class="px-2 py-1 bg-surface border border-border-subtle rounded text-xs text-on-surface flex items-center gap-1 hover:border-primary transition-colors cursor-default"><span class="material-symbols-outlined text-[14px]">balcony</span> Private Balcony</span>
<span class="px-2 py-1 bg-surface border border-border-subtle rounded text-xs text-on-surface flex items-center gap-1 hover:border-primary transition-colors cursor-default"><span class="material-symbols-outlined text-[14px]">fitness_center</span> Gym in Bldg</span>
<span class="px-2 py-1 bg-surface border border-border-subtle rounded text-xs text-on-surface flex items-center gap-1 hover:border-primary transition-colors cursor-default"><span class="material-symbols-outlined text-[14px]">concierge</span> 24/7 Doorman</span>
<span class="px-2 py-1 bg-surface border border-border-subtle rounded text-xs text-on-surface flex items-center gap-1 hover:border-primary transition-colors cursor-default"><span class="material-symbols-outlined text-[14px]">pets</span> Pets Allowed</span>
</div>
</div>
</div>
<!-- History & Evidence -->
<div class="bg-surface-glass backdrop-blur-xl border border-border-subtle rounded-xl p-4 shadow-sm flex flex-col gap-4">
<h3 class="font-label-caps text-label-caps text-on-surface-variant border-b border-border-subtle pb-2">LISTING HISTORY &amp; EVIDENCE</h3>
<div class="flex gap-4">
<div class="flex-1 bg-surface-container-lowest border border-border-subtle rounded-lg p-3 relative overflow-hidden">
<div class="absolute right-0 top-0 w-1 h-full bg-status-shortlisted"></div>
<div class="font-label-caps text-label-caps text-on-surface-variant mb-1">DAYS ON MARKET</div>
<div class="flex items-end gap-2">
<span class="font-display-table text-2xl text-on-surface leading-none">14</span>
<span class="text-xs text-secondary flex items-center"><span class="material-symbols-outlined text-[14px]">trending_down</span> Fast</span>
</div>
</div>
<div class="flex-1 bg-surface-container-lowest border border-border-subtle rounded-lg p-3 relative overflow-hidden">
<div class="absolute right-0 top-0 w-1 h-full bg-status-warning"></div>
<div class="font-label-caps text-label-caps text-on-surface-variant mb-1">PRICE CHANGE</div>
<div class="flex items-end gap-2">
<span class="font-display-table text-lg text-on-surface leading-none">-$200</span>
<span class="text-xs text-status-warning flex items-center">7 days ago</span>
</div>
</div>
</div>
<!-- Dense Data Table for History -->
<div class="mt-2">
<table class="w-full text-left border-collapse">
<thead>
<tr class="border-b border-border-subtle">
<th class="font-label-caps text-label-caps text-on-surface-variant py-1 font-normal">Date</th>
<th class="font-label-caps text-label-caps text-on-surface-variant py-1 font-normal">Event</th>
<th class="font-label-caps text-label-caps text-on-surface-variant py-1 font-normal text-right">Price</th>
</tr>
</thead>
<tbody>
<tr class="border-b border-border-subtle hover:bg-surface-container transition-colors group cursor-pointer">
<td class="py-1 text-xs text-on-surface">Aug 15, 2023</td>
<td class="py-1 text-xs text-on-surface flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-status-warning"></span> Price Drop</td>
<td class="py-1 text-xs text-on-surface text-right font-semibold">$8,500</td>
</tr>
<tr class="border-b border-border-subtle hover:bg-surface-container transition-colors group cursor-pointer">
<td class="py-1 text-xs text-on-surface">Aug 01, 2023</td>
<td class="py-1 text-xs text-on-surface flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-status-shortlisted"></span> Listed</td>
<td class="py-1 text-xs text-on-surface text-right">$8,700</td>
</tr>
</tbody>
</table>
</div>
</div>
<!-- Review Actions Panel -->
<div class="bg-surface-container-high border border-border-subtle rounded-xl p-4 shadow-sm flex items-center justify-between mt-auto">
<div class="flex items-center gap-3">
<button class="w-10 h-10 rounded-full border border-border-subtle bg-surface hover:bg-surface-variant flex items-center justify-center transition-colors text-on-surface-variant">
<span class="material-symbols-outlined">favorite_border</span>
</button>
<button class="w-10 h-10 rounded-full border border-border-subtle bg-surface hover:bg-surface-variant flex items-center justify-center transition-colors text-on-surface-variant">
<span class="material-symbols-outlined">share</span>
</button>
</div>
<div class="flex gap-3">
<button class="px-4 py-2 bg-surface text-on-surface border border-border-subtle rounded-lg font-display-table text-display-table hover:bg-surface-variant transition-colors">Schedule Tour</button>
<button class="px-6 py-2 bg-primary text-on-primary rounded-lg font-display-table text-display-table shadow-sm hover:bg-primary-container transition-colors flex items-center gap-2">
<span class="material-symbols-outlined text-[18px]">send</span> Contact Agent
                        </button>
</div>
</div>
</div>
<!-- Right Column: Map & Commute -->
<div class="w-5/12 flex flex-col gap-panel-margin">
<!-- Map Container -->
<div class="flex-1 bg-surface-glass backdrop-blur-xl border border-border-subtle rounded-xl overflow-hidden shadow-sm flex flex-col relative">
<div class="absolute top-2 left-2 right-2 flex justify-between items-center z-10 pointer-events-none">
<div class="bg-surface/90 backdrop-blur pointer-events-auto border border-border-subtle rounded px-2 py-1 font-label-caps text-label-caps flex items-center gap-1 shadow-sm">
<span class="w-2 h-2 rounded-full bg-status-shortlisted animate-pulse"></span> Active View
                        </div>
<div class="flex gap-1 pointer-events-auto">
<button class="bg-surface/90 backdrop-blur p-1 rounded border border-border-subtle shadow-sm hover:bg-surface-variant text-on-surface-variant"><span class="material-symbols-outlined text-[16px]">layers</span></button>
<button class="bg-surface/90 backdrop-blur p-1 rounded border border-border-subtle shadow-sm hover:bg-surface-variant text-on-surface-variant"><span class="material-symbols-outlined text-[16px]">my_location</span></button>
</div>
</div>
<!-- Map Graphic -->
<div class="flex-1 relative bg-surface-dim">
<img alt="Property Location Map" class="w-full h-full object-cover" data-alt="A detailed, localized map view of the Tribeca neighborhood in Manhattan. The map is in a clean, enterprise light-mode style, with subtle grey streets, soft white blocks, and distinct blue lines indicating subway routes. A prominent blue marker indicates the property location at 450 Washington St. The design is precise and data-dense, suitable for a real estate professional's dashboard." data-location="Tribeca, NYC" src="https://lh3.googleusercontent.com/aida-public/AB6AXuC7PE_65IUSGASxSvwPqk1O00lec3JXTtZ3FAmwciZHxsAVMI_X20RpqPIgtW2KlkNoqU22WDiIt1Esc9tmJl8caDas2f5W7B_eIMb2zaG4DzEK_OWl46fb6G98b5AWFwvhiU7xK5ez1GVR-LexNHc2YieBVt5IhmJEg48pT0TXRKjr5r2LD7vFAZvUiHZeHSWGpw0XCDk4fzvXkbUMQ0RhdF1rTM5LXAitBSfoY8MbzgLNMXjrLDpw"/>
<!-- Simulated Overlay Marker -->
<div class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
<div class="bg-surface border-l-4 border-status-shortlisted shadow-lg rounded px-2 py-1 flex items-center gap-1">
<span class="font-marker-id text-marker-id text-on-surface">Apt 12B</span>
</div>
<div class="w-1 h-3 bg-status-shortlisted"></div>
<div class="w-2 h-2 rounded-full bg-status-shortlisted ring-2 ring-surface"></div>
</div>
<!-- Transit Nodes Overlays -->
<div class="absolute top-1/3 left-1/4 bg-[#0039A6] text-white w-4 h-4 rounded-full flex items-center justify-center font-bold text-[8px] shadow-sm ring-1 ring-white">A</div>
<div class="absolute bottom-1/4 right-1/3 bg-[#EE352E] text-white w-4 h-4 rounded-full flex items-center justify-center font-bold text-[8px] shadow-sm ring-1 ring-white">1</div>
</div>
</div>
<!-- Commute Analysis -->
<div class="h-64 bg-surface-glass backdrop-blur-xl border border-border-subtle rounded-xl p-4 shadow-sm flex flex-col">
<div class="flex justify-between items-center mb-4 border-b border-border-subtle pb-2">
<h3 class="font-label-caps text-label-caps text-on-surface-variant flex items-center gap-1">
<span class="material-symbols-outlined text-[16px]">commute</span> COMMUTE ANALYSIS
                        </h3>
<button class="text-xs text-primary hover:underline">Edit Hubs</button>
</div>
<div class="flex-1 flex flex-col gap-3 overflow-y-auto pr-2 custom-scrollbar">
<!-- Route 1 -->
<div class="bg-surface-container-lowest border border-border-subtle rounded-lg p-2.5 flex items-center justify-between hover:border-primary transition-colors cursor-default">
<div class="flex items-center gap-3">
<div class="w-8 h-8 rounded bg-surface-container flex items-center justify-center text-on-surface-variant">
<span class="material-symbols-outlined text-[18px]">business_center</span>
</div>
<div>
<div class="font-display-table text-sm text-on-surface">Midtown Office (W 42nd)</div>
<div class="flex items-center gap-1 mt-0.5">
<span class="bg-[#0039A6] text-white w-3 h-3 rounded-full flex items-center justify-center font-bold text-[7px]">A</span>
<span class="bg-[#0039A6] text-white w-3 h-3 rounded-full flex items-center justify-center font-bold text-[7px]">C</span>
<span class="material-symbols-outlined text-[10px] text-on-surface-variant">arrow_forward</span>
<span class="bg-[#EE352E] text-white w-3 h-3 rounded-full flex items-center justify-center font-bold text-[7px]">1</span>
</div>
</div>
</div>
<div class="text-right">
<div class="font-headline-panel text-lg font-bold text-on-surface">22<span class="text-xs font-normal text-on-surface-variant">m</span></div>
<div class="text-[10px] text-secondary flex items-center justify-end gap-0.5 mt-0.5">
<span class="material-symbols-outlined text-[10px]">check_circle</span> High Conf.
                                </div>
</div>
</div>
<!-- Route 2 -->
<div class="bg-surface-container-lowest border border-border-subtle rounded-lg p-2.5 flex items-center justify-between hover:border-primary transition-colors cursor-default">
<div class="flex items-center gap-3">
<div class="w-8 h-8 rounded bg-surface-container flex items-center justify-center text-on-surface-variant">
<span class="material-symbols-outlined text-[18px]">flight_takeoff</span>
</div>
<div>
<div class="font-display-table text-sm text-on-surface">Newark Airport (EWR)</div>
<div class="flex items-center gap-1 mt-0.5">
<span class="bg-[#0039A6] text-white px-1 h-3 rounded flex items-center justify-center font-bold text-[7px]">PATH</span>
<span class="material-symbols-outlined text-[10px] text-on-surface-variant">arrow_forward</span>
<span class="bg-surface-variant text-on-surface-variant border border-border-subtle px-1 h-3 rounded flex items-center justify-center font-bold text-[7px]">NJT</span>
</div>
</div>
</div>
<div class="text-right">
<div class="font-headline-panel text-lg font-bold text-on-surface">45<span class="text-xs font-normal text-on-surface-variant">m</span></div>
<div class="text-[10px] text-status-warning flex items-center justify-end gap-0.5 mt-0.5">
<span class="material-symbols-outlined text-[10px]">info</span> Med Conf.
                                </div>
</div>
</div>
<!-- Walkability -->
<div class="bg-surface-container-lowest border border-border-subtle rounded-lg p-2.5 flex items-center justify-between mt-1">
<div class="flex items-center gap-2">
<span class="material-symbols-outlined text-secondary text-[18px]">directions_walk</span>
<span class="font-display-table text-sm text-on-surface">Walk Score</span>
</div>
<div class="font-headline-panel text-lg font-bold text-secondary">98<span class="text-xs font-normal text-on-surface-variant">/100</span></div>
</div>
</div>
</div>
</div>
</main>
</div>
<style>
        /* Custom Scrollbar for a cleaner look */
        .custom-scrollbar::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
            background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
            background-color: theme('colors.border-subtle');
            border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
            background-color: theme('colors.outline');
        }
    </style>
</body></html>