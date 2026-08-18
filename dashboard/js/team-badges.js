/**
 * team-badges.js
 * Visual branding system for all 14 IPL franchises.
 * Provides brand colors, short codes, and inline SVG shield/crest emblems.
 */

window.IPL_TEAMS = {
  "Chennai Super Kings": {
    short: "CSK",
    primary: "#FCCA06",
    secondary: "#005FA2",
    accent: "#F37023",
    text: "#000000"
  },
  "Mumbai Indians": {
    short: "MI",
    primary: "#004BA0",
    secondary: "#D1AB3E",
    accent: "#00AEEF",
    text: "#FFFFFF"
  },
  "Kolkata Knight Riders": {
    short: "KKR",
    primary: "#3A225D",
    secondary: "#F2C029",
    accent: "#702A8C",
    text: "#FFFFFF"
  },
  "Royal Challengers Bangalore": {
    short: "RCB",
    primary: "#EC1C24",
    secondary: "#E6CA65",
    accent: "#1D1D1B",
    text: "#FFFFFF"
  },
  "Royal Challengers Bengaluru": {
    short: "RCB",
    primary: "#EC1C24",
    secondary: "#E6CA65",
    accent: "#0057B8",
    text: "#FFFFFF"
  },
  "Rajasthan Royals": {
    short: "RR",
    primary: "#EA1B85",
    secondary: "#254AA5",
    accent: "#FFD700",
    text: "#FFFFFF"
  },
  "Sunrisers Hyderabad": {
    short: "SRH",
    primary: "#F26522",
    secondary: "#000000",
    accent: "#FFC20E",
    text: "#FFFFFF"
  },
  "Delhi Capitals": {
    short: "DC",
    primary: "#004792",
    secondary: "#D71921",
    accent: "#00B4D8",
    text: "#FFFFFF"
  },
  "Delhi Daredevils": {
    short: "DD",
    primary: "#D71921",
    secondary: "#004792",
    accent: "#1B2A4A",
    text: "#FFFFFF"
  },
  "Punjab Kings": {
    short: "PBKS",
    primary: "#DD1F2D",
    secondary: "#A7A9AC",
    accent: "#ED1C24",
    text: "#FFFFFF"
  },
  "Kings XI Punjab": {
    short: "KXIP",
    primary: "#B32428",
    secondary: "#C0C0C0",
    accent: "#ED1C24",
    text: "#FFFFFF"
  },
  "Gujarat Titans": {
    short: "GT",
    primary: "#1B2133",
    secondary: "#E3BA64",
    accent: "#00E5FF",
    text: "#FFFFFF"
  },
  "Lucknow Super Giants": {
    short: "LSG",
    primary: "#0057B8",
    secondary: "#FF7000",
    accent: "#A2C514",
    text: "#FFFFFF"
  },
  "Rising Pune Supergiant": {
    short: "RPS",
    primary: "#6B238E",
    secondary: "#FDE100",
    accent: "#D31245",
    text: "#FFFFFF"
  },
  "Rising Pune Supergiants": {
    short: "RPS",
    primary: "#6B238E",
    secondary: "#FDE100",
    accent: "#D31245",
    text: "#FFFFFF"
  },
  "Gujarat Lions": {
    short: "GL",
    primary: "#E05A17",
    secondary: "#B48529",
    accent: "#183262",
    text: "#FFFFFF"
  },
  "Pune Warriors": {
    short: "PWI",
    primary: "#008080",
    secondary: "#000000",
    accent: "#C0C0C0",
    text: "#FFFFFF"
  },
  "Kochi Tuskers Kerala": {
    short: "KTK",
    primary: "#6F2C91",
    secondary: "#FF6600",
    accent: "#FFFFFF",
    text: "#FFFFFF"
  },
  "Deccan Chargers": {
    short: "DC",
    primary: "#263B59",
    secondary: "#D4AF37",
    accent: "#7292B2",
    text: "#FFFFFF"
  }
};

window.getTeamInfo = function(teamName) {
  if (!teamName) return { short: "IPL", primary: "#00FF9D", secondary: "#00E5FF", text: "#000000" };
  const normalized = teamName.trim();
  return window.IPL_TEAMS[normalized] || {
    short: normalized.split(' ').map(w => w[0]).join('').substring(0, 4).toUpperCase(),
    primary: "#3A4D6B",
    secondary: "#00FF9D",
    text: "#FFFFFF"
  };
};

window.renderTeamBadgeSVG = function(teamName, size = 40) {
  const info = window.getTeamInfo(teamName);
  const p = info.primary;
  const s = info.secondary;
  const short = info.short;
  
  return `
    <svg width="${size}" height="${size}" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" class="team-badge-svg" data-team="${teamName}">
      <defs>
        <linearGradient id="grad_${short}_${size}" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${p}" />
          <stop offset="100%" stop-color="${s}" />
        </linearGradient>
        <filter id="glow_${short}_${size}" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="${p}" flood-opacity="0.4"/>
        </filter>
      </defs>
      <!-- Shield Shape -->
      <path d="M50 5 L88 20 V50 C88 74 50 95 50 95 C50 95 12 74 12 50 V20 L50 5 Z" 
            fill="url(#grad_${short}_${size})" 
            stroke="rgba(255,255,255,0.4)" 
            stroke-width="3" 
            filter="url(#glow_${short}_${size})" />
      <!-- Inner Accent Border -->
      <path d="M50 13 L80 25 V48 C80 67 50 84 50 84 C50 84 20 67 20 48 V25 L50 13 Z" 
            fill="none" 
            stroke="rgba(255,255,255,0.25)" 
            stroke-width="1.5" />
      <!-- Team Short Code Text -->
      <text x="50" y="57" 
            font-family="'Outfit', 'Inter', sans-serif" 
            font-weight="900" 
            font-size="${short.length > 3 ? '22' : '26'}" 
            fill="${info.text}" 
            text-anchor="middle" 
            letter-spacing="0.5">
        ${short}
      </text>
    </svg>
  `;
};
