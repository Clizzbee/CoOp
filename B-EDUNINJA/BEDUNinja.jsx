import { useState, useEffect, useRef, useCallback } from "react";

/* ── AUDIO ─────────────────────────────────────────────────────────────────── */
let _ac = null;
const getAC = () => {
  if (!_ac) _ac = new (window.AudioContext || window.webkitAudioContext)();
  return _ac;
};
const tone = (f, type, dur, vol, d) => {
  try {
    const c = getAC(), o = c.createOscillator(), g = c.createGain();
    o.connect(g); g.connect(c.destination);
    o.type = type || "triangle"; o.frequency.value = f;
    const t = c.currentTime + (d || 0);
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(vol || 0.25, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.001, t + (dur || 0.12));
    o.start(t); o.stop(t + (dur || 0.12) + 0.06);
  } catch (e) {}
};
const sfx = {
  slice: () => { tone(820, "sawtooth", 0.055, 0.3); tone(1300, "sine", 0.09, 0.18, 0.04); },
  wrong: () => { tone(180, "sawtooth", 0.22, 0.4); tone(120, "square", 0.18, 0.3, 0.07); },
  combo: (tier) => { [523,659,784,988,1175,1568].slice(0, Math.min(tier+2,6)).forEach((f,i) => tone(f,"triangle",0.13,0.28,i*0.07)); },
  ninja: () => { for (let i=0;i<7;i++) tone(280+i*100,"sine",0.16,0.22,i*0.055); },
  clear: () => { [523,659,784,1047,1319].forEach((f,i) => tone(f,"triangle",0.18,0.32,i*0.09)); },
};

/* ── HELPERS ───────────────────────────────────────────────────────────────── */
const isPrime = (n) => { if (n<2) return false; for (let i=2;i<=Math.sqrt(n);i++) if (n%i===0) return false; return true; };
const shuffle = (a) => { const b=[...a]; for (let i=b.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1));[b[i],b[j]]=[b[j],b[i]]; } return b; };
const pick = (arr, n) => shuffle([...arr]).slice(0, n);
const rand = (arr) => arr[Math.floor(Math.random()*arr.length)];
const hexToRgb = (hex) => {
  const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return r ? (parseInt(r[1],16)+","+parseInt(r[2],16)+","+parseInt(r[3],16)) : "255,215,0";
};

/* ── DATA ──────────────────────────────────────────────────────────────────── */
const VOWELS_LIST = ["A","E","I","O","U"];
const ALL_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

const COLOR_POOL = [
  { v:"RED",    icon:"🔴", tag:"RED",    fg:"#ff5555", bg:"rgba(255,70,70,0.35)" },
  { v:"BLUE",   icon:"🔵", tag:"BLUE",   fg:"#5599ff", bg:"rgba(80,150,255,0.35)" },
  { v:"GREEN",  icon:"🟢", tag:"GREEN",  fg:"#44cc55", bg:"rgba(68,200,80,0.35)" },
  { v:"YELLOW", icon:"🟡", tag:"YELLOW", fg:"#ffdd33", bg:"rgba(255,220,50,0.35)" },
  { v:"ORANGE", icon:"🟠", tag:"ORANGE", fg:"#ff8833", bg:"rgba(255,130,50,0.35)" },
  { v:"PURPLE", icon:"🟣", tag:"PURPLE", fg:"#bb55ff", bg:"rgba(180,80,255,0.35)" },
];

const CVC = {
  A: ["cat","bat","hat","rat","mat","sat","fan","can","man","tap","bag","tag","nap","lap","gap"],
  E: ["bed","red","led","net","jet","set","wet","leg","den","hen","ten","peg","fed","gem","beg"],
  I: ["pig","big","dig","sit","bit","hit","bin","pin","win","fin","tin","lid","tip","zip","dip"],
  O: ["dog","log","fog","hot","lot","pot","got","hop","mop","top","nod","bob","cob","job","sob"],
  U: ["bug","mug","jug","rug","cup","cut","bun","fun","run","sun","gun","pup","rut","tub","dug"],
};
const ALL_CVC = Object.values(CVC).flat();

const SIGHT  = ["the","is","a","it","in","on","at","up","as","be","by","do","go","he","if","me","my","no","of","or","so","to","us","we","and","are","but","for","not","was","his","her","you","she","they","have","with","that","this","from","what","when","were","can","said","had","has","him","look","see","come","who","get","may","now","how","out","one","all","too","any","put","let","did","its","our"];
const NSIGHT = ["frog","lamp","brick","chess","swift","drape","bland","gloom","knack","flint","brash","cleft","stomp","gripe","thud","crisp","scalp","blunt","clamp","strut","dwell","frost","grasp","plunge","spree"];

const ANIMALS    = ["cat","dog","bird","fish","lion","bear","frog","wolf","deer","owl","ant","bee","rat","fox","crab","duck","pig","hen","cow","ape","ram","elk","bat","jay","emu"];
const FOOD       = ["cake","rice","soup","corn","bean","pear","plum","lime","milk","egg","bread","pie","jam","nut","fig","oat","tart","bun","chip","meat","yam","kale","beet","leek","toast"];
const NATURE_W   = ["tree","rock","star","moon","fire","wind","rain","snow","lake","leaf","rose","vine","cave","mist","wave","seed","clay","dusk","dawn","frost","hill","reef","bog","peak","vale"];
const VERBS      = ["run","jump","swim","fly","read","sing","dance","eat","play","think","dream","build","cook","leap","dive","spin","soar","skip","clap","wave","push","pull","kick","hunt","roam"];
const NOUNS      = [...ANIMALS,...NATURE_W,"house","car","door","desk","cup","hat","bag","book","hand","foot","eye","arm","sky","sea","wall","road","path","town","farm"];
const ADJECTIVES = ["big","small","fast","slow","hot","cold","old","new","soft","hard","long","short","dark","bright","sweet","sour","kind","brave","wise","loud","quiet","sharp","bold","calm","wild"];

const PRAISE = ["AMAZING!", "SUPER STAR!", "BRILLIANT!", "AWESOME!", "FANTASTIC!", "GREAT JOB!", "YOU DID IT!"];

/* ── TILE FACTORIES ─────────────────────────────────────────────────────────── */
const mkTile = (display, isCorrect, id, meta) => ({
  id, display:String(display), isCorrect, state:"idle", meta:meta||{}
});

function makeColorTiles(tag) {
  const target = COLOR_POOL.find(c => c.tag===tag);
  const others  = COLOR_POOL.filter(c => c.tag!==tag);
  const correct = Array.from({length:6}, (_,i) => mkTile(target.icon+" "+target.v, true, i, {fg:target.fg, bg:target.bg, fs:13}));
  const wrong = [];
  for (let i=0; wrong.length<19; i++) {
    const c = others[i % others.length];
    wrong.push(mkTile(c.icon+" "+c.v, false, 6+i, {fg:c.fg, bg:c.bg, fs:13}));
  }
  return shuffle([...correct,...wrong]).slice(0,25).map((t,i) => ({...t, id:i}));
}

function makeLetterTiles(target) {
  const isVowels = target==="VOWELS";
  const check = isVowels ? l=>VOWELS_LIST.includes(l) : l=>l===target;
  const correct = isVowels ? [...VOWELS_LIST,...VOWELS_LIST] : Array.from({length:7}, ()=>target);
  const wrong = pick(ALL_LETTERS.filter(l=>!check(l)), 18);
  const tiles = [
    ...correct.map((l,i) => mkTile(l, true, i, {fs:30})),
    ...wrong.map((l,i) => mkTile(l, false, i+correct.length, {fs:30})),
  ];
  return shuffle(tiles).slice(0,25).map((t,i) => ({...t, id:i}));
}

function makeWordTiles(correct, wrong) {
  const c = pick(correct, Math.min(7, correct.length));
  const filtered = wrong.filter(x => !correct.includes(x));
  const w = pick(filtered, Math.min(18, filtered.length));
  const all = shuffle([
    ...c.map((v,i) => mkTile(v, true, i)),
    ...w.map((v,i) => mkTile(v, false, i+7)),
  ]).slice(0,25);
  if (!all.some(t => t.isCorrect) && correct.length>0) {
    all[0] = mkTile(correct[0], true, 0);
  }
  return all.map((t,i) => ({...t, id:i}));
}

function makeNumTiles(check, min, max) {
  const nums = Array.from({length:max-min+1}, (_,i) => i+min);
  const valids = nums.filter(check);
  const invalids = nums.filter(n => !check(n));
  if (!valids.length) return makeNumTiles(n=>n%2===0, 1, 25);
  const c = pick(valids, Math.min(7, valids.length));
  const w = pick(invalids, Math.min(18, invalids.length));
  return shuffle([
    ...c.map((v,i) => mkTile(v, true, i)),
    ...w.map((v,i) => mkTile(v, false, i+7)),
  ]).slice(0,25).map((t,i) => ({...t, id:i}));
}

/* ── STAGES ─────────────────────────────────────────────────────────────────── */
const STAGES = [
  {
    id:0, name:"COLORS", sub:"Pre-Reader · Age 3+", icon:"🎨", accent:"#ff6b6b", hint:3, time:0,
    desc:"No reading needed! Find tiles by their color!",
    challenges: COLOR_POOL.map(ct => ({
      label:"Find all the "+ct.tag+" tiles!",
      build:()=>makeColorTiles(ct.tag)
    }))
  },
  {
    id:1, name:"LETTERS", sub:"Know Your ABCs · Age 4+", icon:"🔤", accent:"#ffb3b3", hint:3, time:180,
    desc:"Recognize letters! Big and easy to read!",
    challenges:[
      { label:"Find all the VOWELS!  ( A  E  I  O  U )", build:()=>makeLetterTiles("VOWELS") },
      ...["B","C","D","F","G","H","M","P","R","S","T"].map(l => ({
        label:"Find the letter  "+l+"!",
        build:()=>makeLetterTiles(l)
      }))
    ]
  },
  {
    id:2, name:"PHONICS", sub:"Short Vowel Sounds · Age 5+", icon:"💬", accent:"#ffcc55", hint:2, time:150,
    desc:"Listen for the vowel sounds inside words!",
    challenges:[
      { label:'Words with short A — cat, bat, hat...', build:()=>makeWordTiles(CVC.A,[...CVC.E,...CVC.I,...CVC.O,...CVC.U]) },
      { label:'Words with short E — bed, red, ten...', build:()=>makeWordTiles(CVC.E,[...CVC.A,...CVC.I,...CVC.O,...CVC.U]) },
      { label:'Words with short I — pig, sit, win...', build:()=>makeWordTiles(CVC.I,[...CVC.A,...CVC.E,...CVC.O,...CVC.U]) },
      { label:'Words with short O — dog, hot, mop...', build:()=>makeWordTiles(CVC.O,[...CVC.A,...CVC.E,...CVC.I,...CVC.U]) },
      { label:'Words with short U — bug, cup, run...', build:()=>makeWordTiles(CVC.U,[...CVC.A,...CVC.E,...CVC.I,...CVC.O]) },
      { label:"Words that START with  B!", build:()=>makeWordTiles(ALL_CVC.filter(w=>w[0]==="b"), ALL_CVC.filter(w=>w[0]!=="b")) },
      { label:"Words that START with  S!", build:()=>makeWordTiles(ALL_CVC.filter(w=>w[0]==="s"), ALL_CVC.filter(w=>w[0]!=="s")) },
      { label:"Words that END in  -AT!", build:()=>makeWordTiles(ALL_CVC.filter(w=>w.endsWith("at")), ALL_CVC.filter(w=>!w.endsWith("at"))) },
    ]
  },
  {
    id:3, name:"SIGHT WORDS", sub:"High-Frequency Words · Age 5-6", icon:"📚", accent:"#88ff88", hint:2, time:120,
    desc:"Find the common words you see every single day!",
    challenges:[
      { label:"Find the SIGHT WORDS!", build:()=>makeWordTiles(SIGHT, NSIGHT) },
      { label:"Find SHORT words — 3 letters or fewer!", build:()=>{ const p=[...SIGHT,...ALL_CVC]; return makeWordTiles(p.filter(w=>w.length<=3), p.filter(w=>w.length>3)); } },
      { label:"Find words that START with a VOWEL!", build:()=>{ const p=[...NOUNS,...VERBS,...SIGHT]; return makeWordTiles(p.filter(w=>/^[aeiou]/i.test(w)), p.filter(w=>!/^[aeiou]/i.test(w))); } },
    ]
  },
  {
    id:4, name:"CATEGORIES", sub:"Word Groups · Age 6+", icon:"🐾", accent:"#66ddff", hint:1, time:110,
    desc:"Sort words into the right groups!",
    challenges:[
      { label:"Find all the ANIMALS!", build:()=>makeWordTiles(ANIMALS,[...FOOD,...NATURE_W,...ADJECTIVES]) },
      { label:"Find all FOOD words!", build:()=>makeWordTiles(FOOD,[...ANIMALS,...NATURE_W,...VERBS]) },
      { label:"Find NATURE words!", build:()=>makeWordTiles(NATURE_W,[...ANIMALS,...FOOD,...ADJECTIVES]) },
      { label:"Find DESCRIBING words — adjectives!", build:()=>makeWordTiles(ADJECTIVES,[...ANIMALS,...FOOD,...VERBS]) },
    ]
  },
  {
    id:5, name:"GRAMMAR", sub:"Parts of Speech · Age 7+", icon:"📝", accent:"#aaccff", hint:1, time:100,
    desc:"Identify verbs, nouns, and adjectives!",
    challenges:[
      { label:"Find ACTION WORDS — verbs!", build:()=>makeWordTiles(VERBS,[...NOUNS,...ADJECTIVES]) },
      { label:"Find THING WORDS — nouns!", build:()=>makeWordTiles(NOUNS,[...VERBS,...ADJECTIVES]) },
      { label:"Find DESCRIBING WORDS — adjectives!", build:()=>makeWordTiles(ADJECTIVES,[...NOUNS,...VERBS]) },
      { label:"Find words with MORE than 4 letters!", build:()=>{ const p=[...NOUNS,...VERBS,...ADJECTIVES]; return makeWordTiles(p.filter(w=>w.length>4), p.filter(w=>w.length<=4)); } },
    ]
  },
  {
    id:6, name:"COUNTING", sub:"Numbers 1-10 · Age 6+", icon:"🔢", accent:"#ffaaff", hint:1, time:100,
    desc:"Get comfortable with numbers!",
    challenges:[
      { label:"Find numbers LESS THAN 5!", build:()=>makeNumTiles(n=>n<5, 1, 10) },
      { label:"Find numbers GREATER THAN 5!", build:()=>makeNumTiles(n=>n>5, 1, 10) },
      { label:"Find EVEN numbers!  2, 4, 6, 8, 10", build:()=>makeNumTiles(n=>n%2===0, 1, 10) },
      { label:"Find ODD numbers!  1, 3, 5, 7, 9", build:()=>makeNumTiles(n=>n%2!==0, 1, 10) },
      { label:"Find numbers from 6 to 10!", build:()=>makeNumTiles(n=>n>=6, 1, 10) },
    ]
  },
  {
    id:7, name:"BASIC MATH", sub:"Even, Odd and Patterns · Age 7+", icon:"🔣", accent:"#ffdd88", hint:0, time:90,
    desc:"Master even, odd, and skip counting!",
    challenges:[
      { label:"Find EVEN numbers!", build:()=>makeNumTiles(n=>n%2===0, 1, 20) },
      { label:"Find ODD numbers!", build:()=>makeNumTiles(n=>n%2!==0, 1, 20) },
      { label:"Find MULTIPLES OF 2!", build:()=>makeNumTiles(n=>n%2===0, 1, 30) },
      { label:"Find MULTIPLES OF 3!", build:()=>makeNumTiles(n=>n%3===0, 1, 30) },
      { label:"Find MULTIPLES OF 5!", build:()=>makeNumTiles(n=>n%5===0, 1, 40) },
      { label:"Find numbers GREATER THAN 15!", build:()=>makeNumTiles(n=>n>15, 1, 30) },
    ]
  },
  {
    id:8, name:"MULTIPLES", sub:"Times Tables · Age 8+", icon:"×", accent:"#ff9966", hint:0, time:80,
    desc:"Master every multiplication pattern!",
    challenges:[
      { label:"Find MULTIPLES OF 4!", build:()=>makeNumTiles(n=>n%4===0, 1, 50) },
      { label:"Find MULTIPLES OF 6!", build:()=>makeNumTiles(n=>n%6===0, 1, 60) },
      { label:"Find MULTIPLES OF 7!", build:()=>makeNumTiles(n=>n%7===0, 1, 70) },
      { label:"Find MULTIPLES OF 8!", build:()=>makeNumTiles(n=>n%8===0, 1, 80) },
      { label:"Find MULTIPLES OF 9!", build:()=>makeNumTiles(n=>n%9===0, 1, 90) },
      { label:"Find PRIME NUMBERS under 30!", build:()=>makeNumTiles(isPrime, 1, 30) },
    ]
  },
  {
    id:9, name:"ADVANCED", sub:"Elite Patterns · Age 10+", icon:"🧠", accent:"#cc88ff", hint:0, time:65,
    desc:"Elite pattern recognition — no hints, no mercy!",
    challenges:[
      { label:"Find PRIME NUMBERS!", build:()=>makeNumTiles(isPrime, 1, 70) },
      { label:"Find PERFECT SQUARES!", build:()=>makeNumTiles(n=>[1,4,9,16,25,36,49,64].includes(n), 1, 70) },
      { label:"Find multiples of BOTH 2 AND 3!", build:()=>makeNumTiles(n=>n%2===0&&n%3===0, 1, 60) },
      { label:"Find multiples of NEITHER 2 NOR 3!", build:()=>makeNumTiles(n=>n%2!==0&&n%3!==0, 2, 60) },
      { label:"Find MULTIPLES OF 11!", build:()=>makeNumTiles(n=>n%11===0, 1, 99) },
      { label:"Digits that SUM TO 9!", build:()=>makeNumTiles(n=>String(n).split("").reduce((a,d)=>a+Number(d),0)===9, 10, 99) },
    ]
  },
];

/* ── COMBO TIERS ─────────────────────────────────────────────────────────────── */
const TIERS = [
  { min:20, label:"NINJA GOD!",   color:"#00ffee", tier:5 },
  { min:12, label:"ULTRA COMBO!", color:"#ff00cc", tier:4 },
  { min:8,  label:"SUPER COMBO!", color:"#ff6600", tier:3 },
  { min:5,  label:"COMBO!",       color:"#ffd700", tier:2 },
  { min:3,  label:"NICE!",        color:"#88ff88", tier:1 },
];
const getTier = (c) => TIERS.find(t => c>=t.min);

/* ── GLOBAL CSS ──────────────────────────────────────────────────────────────── */
const GCSS = `
  @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');
  * { box-sizing:border-box; margin:0; padding:0; }
  button { outline:none; }
  @keyframes twinkle { 0%,100%{opacity:0.12} 50%{opacity:0.9} }
  @keyframes titleFloat { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
  @keyframes tileIn { from{transform:scale(0) rotate(18deg);opacity:0} to{transform:scale(1);opacity:1} }
  @keyframes tileFloat {
    0%,100%{transform:translateY(0) rotate(0deg)}
    33%{transform:translateY(-4px) rotate(0.8deg)}
    66%{transform:translateY(2px) rotate(-0.8deg)}
  }
  @keyframes tileSlash {
    0%{transform:scale(1);opacity:1;filter:brightness(1)}
    30%{transform:scale(1.25) rotate(-8deg);filter:brightness(3) hue-rotate(60deg)}
    70%{transform:scale(0.6) translateY(-30px);opacity:0.4}
    100%{transform:scale(0) translateY(-50px);opacity:0}
  }
  @keyframes tileWrong {
    0%{transform:scale(1)}
    20%{transform:scale(1.15);filter:brightness(2) saturate(3)}
    50%{transform:scale(0.85) translate(4px,-4px)}
    80%{filter:brightness(0.4) blur(2px)}
    100%{transform:scale(0);opacity:0;filter:blur(6px)}
  }
  @keyframes bannerPop {
    0%{transform:translateX(-50%) scale(0.4);opacity:0}
    15%{transform:translateX(-50%) scale(1.15)}
    25%{transform:translateX(-50%) scale(1)}
    70%{transform:translateX(-50%) scale(1);opacity:1}
    100%{transform:translateX(-50%) scale(0.8);opacity:0}
  }
  @keyframes screenShake {
    0%,100%{transform:none}
    20%{transform:translateX(-8px) rotate(-0.5deg)}
    40%{transform:translateX(8px) rotate(0.5deg)}
    60%{transform:translateX(-5px)}
    80%{transform:translateX(4px)}
  }
  @keyframes urgentPulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  @keyframes ninjaPulse { 0%,100%{opacity:0.8} 50%{opacity:1} }
  @keyframes fadeIn { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:translateY(0)} }
`;

/* ── STAR FIELD ──────────────────────────────────────────────────────────────── */
const STAR_DATA = Array.from({length:80}, (_,i) => ({
  id:i, x:Math.random()*100, y:Math.random()*100,
  size:Math.random()*1.8+0.3, dur:2+Math.random()*4, delay:Math.random()*6,
}));

function StarField() {
  return (
    <div style={{position:"absolute",inset:0,overflow:"hidden",zIndex:0,pointerEvents:"none"}}>
      {STAR_DATA.map(s => (
        <div key={s.id} style={{
          position:"absolute", left:s.x+"%", top:s.y+"%",
          width:s.size, height:s.size, borderRadius:"50%", background:"white",
          animation:"twinkle "+s.dur+"s "+s.delay+"s ease-in-out infinite",
        }}/>
      ))}
    </div>
  );
}

/* ── PARTICLE (JS transition-based, no CSS vars) ────────────────────────────── */
function Particle({ p }) {
  const [gone, setGone] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setGone(true), 30);
    return () => clearTimeout(id);
  }, []);
  const tx = Math.cos(p.angle) * p.dist;
  const ty = Math.sin(p.angle) * p.dist;
  return (
    <div style={{
      position:"absolute",
      left:p.ox, top:p.oy,
      width:p.size, height:p.size,
      borderRadius:"50%",
      background:p.color,
      boxShadow:"0 0 "+(p.size*2)+"px "+p.color,
      transform:gone
        ? "translate(calc(-50% + "+tx+"px), calc(-50% + "+ty+"px)) scale(0)"
        : "translate(-50%, -50%) scale(1)",
      opacity:gone?0:1,
      transition:"transform 0.8s ease-out, opacity 0.8s ease-out",
      pointerEvents:"none",
    }}/>
  );
}

function ParticleLayer({ particles }) {
  if (!particles.length) return null;
  return (
    <div style={{position:"absolute",inset:0,pointerEvents:"none",zIndex:50,overflow:"hidden"}}>
      {particles.map(p => <Particle key={p.id} p={p}/>)}
    </div>
  );
}

/* ── TILE ────────────────────────────────────────────────────────────────────── */
function Tile({ tile, ninjaMode, hintLevel, onClick }) {
  const { fg, bg:metaBg, fs:metaFs } = tile.meta;
  const len = tile.display.length;
  const fontSize = metaFs || (len===1?30:len<=3?18:len<=5?14:len<=7?11:9);
  const showHint = hintLevel>0 && tile.isCorrect && tile.state==="idle";

  let boxShadow;
  if (showHint && hintLevel>=3) {
    boxShadow = "0 0 0 3px #ffd700, 0 0 20px rgba(255,215,0,0.55)";
  } else if (showHint && hintLevel>=2) {
    boxShadow = "0 0 0 1.5px rgba(255,215,0,0.45), 0 0 12px rgba(255,215,0,0.3)";
  } else if (showHint) {
    boxShadow = "0 0 8px rgba(255,215,0,0.2)";
  } else if (ninjaMode) {
    boxShadow = "0 6px 24px rgba(0,0,0,0.6), 0 0 12px rgba(0,255,238,0.12)";
  } else {
    boxShadow = "0 6px 24px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.04)";
  }

  const bg = metaBg || (ninjaMode
    ? "linear-gradient(135deg,rgba(0,18,28,0.9),rgba(0,30,45,0.85))"
    : "linear-gradient(135deg,rgba(18,8,35,0.9),rgba(25,12,50,0.85))");

  let border;
  if (showHint && hintLevel>=3) border = "2px solid #ffd700";
  else if (ninjaMode) border = "1.5px solid rgba(0,255,238,0.4)";
  else border = "1.5px solid rgba(180,120,255,0.18)";

  const color = fg || (ninjaMode ? "#b8fff8" : "#e0d8f8");

  const floatDur   = 3 + (tile.id*0.17)%2.2;
  const floatDelay = (tile.id*0.23)%3.5;
  const spawnDelay = tile.id*0.025;

  let anim;
  if (tile.state==="idle") {
    anim = "tileIn 0.35s "+spawnDelay+"s both, tileFloat "+floatDur+"s "+floatDelay+"s ease-in-out infinite";
  } else if (tile.state==="correct") {
    anim = "tileSlash 0.42s ease-out forwards";
  } else if (tile.state==="wrong") {
    anim = "tileWrong 0.5s ease-out forwards";
  } else {
    anim = "none";
  }

  return (
    <div
      onClick={tile.state==="idle" ? onClick : undefined}
      style={{
        width:90, height:74,
        display:"flex", alignItems:"center", justifyContent:"center",
        borderRadius:10, background:bg, border,
        backdropFilter:"blur(10px)", boxShadow,
        fontSize, fontWeight:700, color,
        fontFamily:'"Rajdhani",sans-serif',
        letterSpacing:len===1?0:1.5,
        userSelect:"none",
        cursor:tile.state==="idle"?"pointer":"default",
        transition:"border-color 0.3s, box-shadow 0.3s",
        animation:anim,
        opacity:tile.state==="cleared"?0:1,
        textShadow:(showHint && hintLevel>=3)?"0 0 8px #ffd700":"none",
        textAlign:"center", lineHeight:1.2,
      }}
    >
      {tile.display}
    </div>
  );
}

/* ── HUD ─────────────────────────────────────────────────────────────────────── */
function HUD({ score, combo, stageName, stageAccent, challNum, total, timeLeft, noTimer, ninjaMode, comboTier }) {
  const tc = timeLeft<10?"#ff3333":timeLeft<20?"#ff8800":"#ffffff";
  return (
    <div style={{position:"absolute",top:0,left:0,right:0,zIndex:30,display:"flex",justifyContent:"space-between",alignItems:"flex-start",padding:"14px 22px",background:"linear-gradient(to bottom,rgba(0,0,0,0.75),transparent)"}}>
      <div>
        <div style={{fontSize:9,letterSpacing:4,color:"#444",textTransform:"uppercase",fontFamily:'"Rajdhani",sans-serif'}}>Score</div>
        <div style={{fontSize:28,fontWeight:900,color:"#ffd700",textShadow:"0 0 16px rgba(255,215,0,0.4)",fontFamily:'"Rajdhani",sans-serif',lineHeight:1}}>
          {score.toLocaleString()}
        </div>
      </div>
      <div style={{textAlign:"center"}}>
        <div style={{fontSize:11,fontWeight:700,color:stageAccent,letterSpacing:3,fontFamily:'"Rajdhani",sans-serif'}}>
          {stageName}
        </div>
        <div style={{fontSize:9,color:"#555",letterSpacing:2,fontFamily:'"Rajdhani",sans-serif',marginTop:2}}>
          {"CH "+challNum+" / "+total}
        </div>
        {combo>0 && (
          <div style={{fontSize:16,fontWeight:700,color:comboTier?comboTier.color:"#777",fontFamily:'"Rajdhani",sans-serif',marginTop:2}}>
            {"x"+combo+" CHAIN"}
          </div>
        )}
      </div>
      <div style={{textAlign:"right"}}>
        {noTimer
          ? <div style={{fontSize:10,color:"#445",letterSpacing:2,fontFamily:'"Rajdhani",sans-serif',marginTop:8}}>take your time</div>
          : <>
              <div style={{fontSize:9,letterSpacing:4,color:"#444",textTransform:"uppercase",fontFamily:'"Rajdhani",sans-serif'}}>Time</div>
              <div style={{fontSize:28,fontWeight:900,color:tc,fontFamily:'"Rajdhani",sans-serif',lineHeight:1,animation:timeLeft<10?"urgentPulse 0.5s ease-in-out infinite":"none"}}>
                {timeLeft}s
              </div>
            </>
        }
      </div>
    </div>
  );
}

/* ── MOMENTUM BAR ────────────────────────────────────────────────────────────── */
function MomentumBar({ momentum, ninjaMode }) {
  return (
    <div style={{position:"absolute",bottom:22,left:"50%",transform:"translateX(-50%)",width:280,zIndex:30}}>
      <div style={{
        fontSize:9, letterSpacing:4, color:ninjaMode?"#00ffee":"#444",
        textAlign:"center", marginBottom:5, textTransform:"uppercase",
        fontFamily:'"Rajdhani",sans-serif', transition:"color 0.3s",
        animation:ninjaMode?"ninjaPulse 0.9s ease-in-out infinite":"none",
      }}>
        {ninjaMode ? "NINJA MODE ACTIVE" : "momentum"}
      </div>
      <div style={{height:5,background:"rgba(255,255,255,0.08)",borderRadius:3,overflow:"hidden",border:"1px solid "+(ninjaMode?"rgba(0,255,238,0.3)":"rgba(255,255,255,0.08)")}}>
        <div style={{
          height:"100%", width:momentum+"%",
          background:ninjaMode?"linear-gradient(90deg,#00ffee,#0088ff)":"linear-gradient(90deg,#ffd700,#ff6600)",
          borderRadius:3, transition:"width 0.25s ease, background 0.4s",
          boxShadow:ninjaMode?"0 0 8px #00ffee":"none",
        }}/>
      </div>
    </div>
  );
}

/* ── BANNER ──────────────────────────────────────────────────────────────────── */
function Banner({ text, color }) {
  return (
    <div style={{position:"absolute",top:"30%",left:"50%",transform:"translateX(-50%)",zIndex:60,pointerEvents:"none",animation:"bannerPop 1.4s ease-out forwards",whiteSpace:"nowrap"}}>
      <div style={{fontSize:44,fontWeight:900,color,textShadow:"0 0 30px "+color,fontFamily:'"Cinzel",serif',letterSpacing:3}}>
        {text}
      </div>
    </div>
  );
}

/* ── MENU SCREEN ─────────────────────────────────────────────────────────────── */
function MenuScreen({ onJourney, onChooseStage }) {
  const [hov, setHov] = useState(null);
  const btns = [
    { id:"journey", label:"START JOURNEY", sub:"Begin from Stage 1 - Colors", icon:"🚀", primary:true,  fn:onJourney },
    { id:"stages",  label:"CHOOSE STAGE",  sub:"Pick any of 10 stages",       icon:"📍", primary:false, fn:onChooseStage },
  ];
  return (
    <div style={{width:"100%",height:"100vh",overflow:"hidden",background:"radial-gradient(ellipse at 50% 0%,#1a0a2e 0%,#0a0614 55%,#020008 100%)",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",position:"relative"}}>
      <style dangerouslySetInnerHTML={{__html:GCSS}}/>
      <StarField/>
      <div style={{textAlign:"center",marginBottom:52,zIndex:10}}>
        <div style={{display:"flex",gap:6,justifyContent:"center",alignItems:"baseline",marginBottom:8}}>
          <span style={{fontSize:72,fontWeight:900,fontFamily:'"Cinzel",serif',background:"linear-gradient(135deg,#ffd700,#ff8800)",WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",animation:"titleFloat 2s ease-in-out infinite",display:"inline-block"}}>B</span>
          <span style={{fontSize:42,fontWeight:700,fontFamily:'"Cinzel",serif',color:"rgba(255,215,0,0.4)",paddingBottom:8}}>.</span>
          <span style={{fontSize:72,fontWeight:900,fontFamily:'"Cinzel",serif',background:"linear-gradient(135deg,#00ffee,#0088ff)",WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",animation:"titleFloat 2.1s 0.2s ease-in-out infinite",display:"inline-block"}}>EDU</span>
        </div>
        <div style={{display:"flex",gap:5,justifyContent:"center"}}>
          {["N","I","N","J","A"].map((ch,i) => (
            <span key={i} style={{
              fontSize:66, fontWeight:900, fontFamily:'"Cinzel",serif',
              background:"linear-gradient(135deg,#ff00cc "+(i*18)+"%, #8800ff "+(40+i*10)+"%)",
              WebkitBackgroundClip:"text", WebkitTextFillColor:"transparent",
              display:"inline-block",
              animation:"titleFloat "+(1.9+i*0.15)+"s "+(0.4+i*0.1)+"s ease-in-out infinite",
            }}>{ch}</span>
          ))}
        </div>
        <div style={{fontSize:10,letterSpacing:5,color:"#445",fontFamily:'"Rajdhani",sans-serif',marginTop:10}}>
          BEGINNER TO ADVANCED  ·  10 STAGES  ·  EVERY AGE
        </div>
      </div>

      <div style={{display:"flex",gap:18,zIndex:10}}>
        {btns.map(btn => {
          const isHov = hov===btn.id;
          const btnBg   = btn.primary ? (isHov?"rgba(255,215,0,0.12)":"rgba(255,215,0,0.05)") : (isHov?"rgba(0,255,238,0.12)":"rgba(0,255,238,0.05)");
          const btnLine = btn.primary ? (isHov?"1.5px solid rgba(255,215,0,0.7)":"1.5px solid rgba(255,215,0,0.18)") : (isHov?"1.5px solid rgba(0,255,238,0.5)":"1.5px solid rgba(0,255,238,0.15)");
          const btnGlow = btn.primary ? (isHov?"0 0 28px rgba(255,215,0,0.12)":"0 8px 32px rgba(0,0,0,0.4)") : (isHov?"0 0 28px rgba(0,255,238,0.1)":"0 8px 32px rgba(0,0,0,0.4)");
          return (
            <button key={btn.id}
              onMouseEnter={()=>setHov(btn.id)}
              onMouseLeave={()=>setHov(null)}
              onClick={btn.fn}
              style={{
                padding:"22px 40px", border:"none", cursor:"pointer",
                borderRadius:14, textAlign:"center", backdropFilter:"blur(14px)",
                transition:"all 0.25s", transform:isHov?"translateY(-4px)":"none",
                background:btnBg, outline:btnLine, boxShadow:btnGlow,
              }}>
              <div style={{fontSize:28,marginBottom:8}}>{btn.icon}</div>
              <div style={{fontSize:13,fontWeight:700,letterSpacing:3,color:isHov?(btn.primary?"#ffd700":"#00ffee"):"#888",fontFamily:'"Cinzel",serif',transition:"color 0.25s"}}>
                {btn.label}
              </div>
              <div style={{fontSize:9,opacity:0.4,marginTop:5,fontFamily:'"Rajdhani",sans-serif',letterSpacing:2,color:"#aaa"}}>
                {btn.sub}
              </div>
            </button>
          );
        })}
      </div>

      <div style={{position:"absolute",bottom:24,fontSize:9,color:"#333",letterSpacing:3,fontFamily:'"Rajdhani",sans-serif',zIndex:10}}>
        Colors · Letters · Phonics · Sight Words · Categories · Grammar · Counting · Math · Multiples · Advanced
      </div>
    </div>
  );
}

/* ── STAGE SELECT ────────────────────────────────────────────────────────────── */
function StageSelect({ onSelect, onBack }) {
  const [hov, setHov] = useState(null);
  return (
    <div style={{width:"100%",height:"100vh",overflowY:"auto",background:"radial-gradient(ellipse at 50% 0%,#1a0a2e 0%,#0a0614 55%,#020008 100%)",display:"flex",flexDirection:"column",alignItems:"center",padding:"32px 24px 48px",position:"relative"}}>
      <style dangerouslySetInnerHTML={{__html:GCSS}}/>
      <StarField/>
      <button onClick={onBack} style={{position:"absolute",top:20,left:20,background:"rgba(255,255,255,0.05)",outline:"1px solid rgba(255,255,255,0.1)",border:"none",color:"#666",borderRadius:8,padding:"8px 16px",cursor:"pointer",fontSize:11,letterSpacing:3,fontFamily:'"Rajdhani",sans-serif',zIndex:10}}>
        back
      </button>
      <div style={{textAlign:"center",marginBottom:28,zIndex:10,marginTop:8}}>
        <div style={{fontSize:26,fontWeight:900,fontFamily:'"Cinzel",serif',color:"#ffd700"}}>THE LEARNING PATH</div>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(230px,1fr))",gap:14,maxWidth:860,width:"100%",zIndex:10}}>
        {STAGES.map(st => {
          const isHov = hov===st.id;
          const rgb = hexToRgb(st.accent);
          return (
            <div key={st.id}
              onMouseEnter={()=>setHov(st.id)}
              onMouseLeave={()=>setHov(null)}
              onClick={()=>onSelect(st.id)}
              style={{
                padding:"18px 20px", borderRadius:12, cursor:"pointer",
                backdropFilter:"blur(10px)", transition:"all 0.2s",
                background:isHov?"rgba("+rgb+",0.1)":"rgba(255,255,255,0.04)",
                outline:"1.5px solid "+(isHov?st.accent+"99":"rgba(255,255,255,0.08)"),
                border:"none",
                transform:isHov?"translateY(-3px) scale(1.01)":"none",
                boxShadow:isHov?"0 0 20px rgba("+rgb+",0.12), 0 8px 32px rgba(0,0,0,0.4)":"0 4px 16px rgba(0,0,0,0.4)",
              }}>
              <div style={{display:"flex",alignItems:"flex-start",gap:12}}>
                <div style={{fontSize:26,lineHeight:1,marginTop:2}}>{st.icon}</div>
                <div style={{flex:1}}>
                  <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:3}}>
                    <div style={{fontSize:12,fontWeight:700,color:st.accent,fontFamily:'"Cinzel",serif',letterSpacing:2}}>{st.name}</div>
                    <div style={{fontSize:9,color:"#333",fontFamily:'"Rajdhani",sans-serif',background:"rgba(0,0,0,0.3)",padding:"2px 6px",borderRadius:4}}>LV {st.id}</div>
                  </div>
                  <div style={{fontSize:9,color:"#666",letterSpacing:1,fontFamily:'"Rajdhani",sans-serif',marginBottom:5}}>{st.sub}</div>
                  <div style={{fontSize:10,color:"#888",fontFamily:'"Rajdhani",sans-serif',lineHeight:1.5}}>{st.desc}</div>
                  <div style={{display:"flex",gap:4,marginTop:8,flexWrap:"wrap"}}>
                    {st.hint>0 && <span style={{fontSize:8,background:"rgba(255,215,0,0.1)",color:"rgba(255,215,0,0.6)",outline:"1px solid rgba(255,215,0,0.2)",border:"none",borderRadius:10,padding:"2px 7px",letterSpacing:1,fontFamily:'"Rajdhani",sans-serif'}}>hints on</span>}
                    {st.time===0 && <span style={{fontSize:8,background:"rgba(100,255,100,0.1)",color:"rgba(100,255,100,0.6)",outline:"1px solid rgba(100,255,100,0.2)",border:"none",borderRadius:10,padding:"2px 7px",letterSpacing:1,fontFamily:'"Rajdhani",sans-serif'}}>no timer</span>}
                    <span style={{fontSize:8,color:"#444",fontFamily:'"Rajdhani",sans-serif',padding:"2px 4px"}}>{st.challenges.length} challenges</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── SCORE SCREEN ────────────────────────────────────────────────────────────── */
function ScoreScreen({ score, maxCombo, round, stageId, journeyMode, onRestart, onNext, onMenu }) {
  const tier = getTier(maxCombo);
  const rank = maxCombo>=20?"NINJA GOD":maxCombo>=12?"ULTRA NINJA":maxCombo>=8?"MASTER":maxCombo>=5?"ADEPT":maxCombo>=3?"APPRENTICE":"ROOKIE";
  const nextStage = STAGES[stageId+1];
  return (
    <div style={{width:"100%",height:"100vh",overflow:"hidden",background:"radial-gradient(ellipse at 50% 0%,#1a0a2e 0%,#0a0614 55%,#020008 100%)",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",fontFamily:'"Cinzel",serif',color:"white",position:"relative"}}>
      <style dangerouslySetInnerHTML={{__html:GCSS}}/>
      <StarField/>
      <div style={{zIndex:10,textAlign:"center",animation:"fadeIn 0.5s ease-out both"}}>
        <div style={{fontSize:10,letterSpacing:5,color:"#444",marginBottom:14,fontFamily:'"Rajdhani",sans-serif',textTransform:"uppercase"}}>Stage Complete</div>
        <div style={{fontSize:78,fontWeight:900,lineHeight:1,marginBottom:6,background:"linear-gradient(135deg,#ffd700,#ff6600)",WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>
          {score.toLocaleString()}
        </div>
        <div style={{fontSize:10,letterSpacing:5,color:"#555",marginBottom:40,fontFamily:'"Rajdhani",sans-serif',textTransform:"uppercase"}}>Final Score</div>
        <div style={{display:"flex",gap:44,justifyContent:"center",marginBottom:40}}>
          {[
            {label:"MAX COMBO", value:"x"+maxCombo, color:tier?tier.color:"#666"},
            {label:"ROUNDS",    value:round,         color:"#aaa"},
            {label:"RANK",      value:rank,          color:tier?tier.color:"#666"},
          ].map(s => (
            <div key={s.label} style={{textAlign:"center"}}>
              <div style={{fontSize:s.label==="RANK"?14:26,fontWeight:700,color:s.color,fontFamily:'"Rajdhani",sans-serif'}}>{s.value}</div>
              <div style={{fontSize:8,letterSpacing:4,color:"#444",marginTop:5,textTransform:"uppercase",fontFamily:'"Rajdhani",sans-serif'}}>{s.label}</div>
            </div>
          ))}
        </div>
        {journeyMode && nextStage && (
          <div style={{marginBottom:24,padding:"14px 24px",borderRadius:12,background:"rgba(0,255,238,0.05)",outline:"1px solid rgba(0,255,238,0.2)",border:"none"}}>
            <div style={{fontSize:9,color:"rgba(0,255,238,0.5)",letterSpacing:4,marginBottom:5,fontFamily:'"Rajdhani",sans-serif'}}>NEXT STAGE UNLOCKED</div>
            <div style={{fontSize:18,color:"#00ffee",fontWeight:700,letterSpacing:2}}>{nextStage.icon+" "+nextStage.name}</div>
            <div style={{fontSize:9,color:"#555",marginTop:3,fontFamily:'"Rajdhani",sans-serif',letterSpacing:2}}>{nextStage.sub}</div>
          </div>
        )}
        <div style={{display:"flex",gap:12,justifyContent:"center"}}>
          {journeyMode && nextStage && (
            <button onClick={onNext} style={{padding:"12px 28px",fontFamily:'"Cinzel",serif',fontSize:11,fontWeight:700,letterSpacing:3,cursor:"pointer",borderRadius:8,border:"none",outline:"1.5px solid rgba(0,255,238,0.5)",background:"rgba(0,255,238,0.08)",color:"#00ffee"}}>
              NEXT STAGE
            </button>
          )}
          <button onClick={onRestart} style={{padding:"12px 28px",fontFamily:'"Cinzel",serif',fontSize:11,fontWeight:700,letterSpacing:3,cursor:"pointer",borderRadius:8,border:"none",outline:"1.5px solid rgba(255,215,0,0.35)",background:"rgba(255,215,0,0.07)",color:"#ffd700"}}>
            PLAY AGAIN
          </button>
          <button onClick={onMenu} style={{padding:"12px 28px",fontFamily:'"Cinzel",serif',fontSize:11,fontWeight:700,letterSpacing:3,cursor:"pointer",borderRadius:8,border:"none",outline:"1.5px solid rgba(255,255,255,0.12)",background:"rgba(255,255,255,0.04)",color:"#888"}}>
            MENU
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── MAIN ────────────────────────────────────────────────────────────────────── */
export default function BEDUNinja() {
  const [screen,   setScreen]   = useState("menu");
  const [journey,  setJourney]  = useState(false);
  const [stageId,  setStageId]  = useState(0);
  const [challIdx, setChallIdx] = useState(0);
  const [tiles,    setTiles]    = useState([]);
  const [combo,    setCombo]    = useState(0);
  const [maxCombo, setMaxCombo] = useState(0);
  const [score,    setScore]    = useState(0);
  const [momentum, setMomentum] = useState(0);
  const [ninja,    setNinja]    = useState(false);
  const [banner,   setBanner]   = useState(null);
  const [shake,    setShake]    = useState(false);
  const [parts,    setParts]    = useState([]);
  const [round,    setRound]    = useState(1);
  const [timeLeft, setTimeLeft] = useState(90);
  const [trans,    setTrans]    = useState(false);

  const pid    = useRef(0);
  const bannerT = useRef(null);
  const timerR  = useRef(null);
  const ninjaR  = useRef(false);
  const transR  = useRef(false);
  const stageR  = useRef(0);
  const challR  = useRef(0);
  const arenaR  = useRef(null);
  const gridR   = useRef(null);

  ninjaR.current = ninja;
  transR.current = trans;
  stageR.current = stageId;
  challR.current = challIdx;

  const stage     = STAGES[stageId] || STAGES[0];
  const chall     = stage.challenges[challIdx % stage.challenges.length];
  const noTimer   = stage.time===0;
  const comboTier = getTier(combo);

  const flash = useCallback((text, color) => {
    clearTimeout(bannerT.current);
    setBanner({text, color});
    bannerT.current = setTimeout(() => setBanner(null), 1400);
  }, []);

  const spawnParticles = (tileId, good) => {
    const colors = good ? ["#ffd700","#ff9900","#ffffff","#00ffcc"] : ["#ff4444","#ff2222","#cc0000"];
    const count  = good ? 12 : 6;
    let ox = "50%", oy = "50%";
    if (gridR.current && arenaR.current) {
      const cells = gridR.current.children;
      if (cells[tileId]) {
        const cr = arenaR.current.getBoundingClientRect();
        const tr = cells[tileId].getBoundingClientRect();
        ox = (tr.left - cr.left + tr.width/2)+"px";
        oy = (tr.top  - cr.top  + tr.height/2)+"px";
      }
    }
    const ps = Array.from({length:count}, (_,i) => ({
      id:pid.current++,
      ox, oy,
      angle:(i/count)*Math.PI*2 + Math.random()*0.5,
      dist:50 + Math.random()*70,
      color:colors[i%colors.length],
      size:4 + Math.random()*4,
    }));
    setParts(p => [...p, ...ps]);
    setTimeout(() => {
      const ids = new Set(ps.map(x => x.id));
      setParts(p => p.filter(x => !ids.has(x.id)));
    }, 1100);
  };

  useEffect(() => {
    if (screen!=="playing") { clearInterval(timerR.current); return; }
    if (noTimer) return;
    timerR.current = setInterval(() => {
      setTimeLeft(t => { if (t<=1) { clearInterval(timerR.current); return 0; } return t-1; });
      setMomentum(m => { const nm=Math.max(0,m-2.2); if (nm===0) setNinja(false); return nm; });
    }, 1000);
    return () => clearInterval(timerR.current);
  }, [screen, stageId, noTimer]);

  useEffect(() => {
    if (screen==="playing" && timeLeft===0 && !noTimer) setTimeout(()=>setScreen("score"), 350);
  }, [timeLeft, screen, noTimer]);

  useEffect(() => {
    if (screen!=="playing" || transR.current || tiles.length===0) return;
    const rem = tiles.filter(t => t.isCorrect && t.state==="idle");
    if (rem.length===0) {
      sfx.clear();
      setTrans(true);
      const early = stageR.current<=3;
      flash(early ? rand(PRAISE) : "ROUND CLEAR!", early ? "#ffd700" : "#00ffee");
      setTimeout(() => {
        const ni = challR.current+1;
        setChallIdx(ni);
        setRound(r => r+1);
        const st = STAGES[stageR.current];
        const ch = st.challenges[ni % st.challenges.length];
        setTiles(ch.build());
        setTrans(false);
      }, 1300);
    }
  }, [tiles, screen, flash]);

  const startStage = (sid, isJourney) => {
    const st = STAGES[sid];
    setStageId(sid); setJourney(isJourney);
    setScore(0); setCombo(0); setMaxCombo(0);
    setMomentum(0); setNinja(false);
    setRound(1); setTimeLeft(st.time||90);
    setChallIdx(0); setBanner(null);
    setParts([]); setTrans(false);
    setTiles(st.challenges[0].build());
    setScreen("playing");
  };

  const handleTile = (tile) => {
    if (tile.state!=="idle" || transR.current) return;
    if (tile.isCorrect) {
      sfx.slice();
      setCombo(prev => {
        const nc = prev+1;
        const multi = ninjaR.current?2:1;
        setScore(s => s+(100+nc*18)*multi);
        setMaxCombo(m => Math.max(m,nc));
        setMomentum(mom => {
          const nm = Math.min(100, mom+15);
          if (nm>=100 && !ninjaR.current) {
            setNinja(true); sfx.ninja(); flash("NINJA MODE!","#00ffee");
          }
          return nm;
        });
        const tier = getTier(nc);
        if (tier) { sfx.combo(tier.tier); if(nc%3===0||nc<6) flash(tier.label,tier.color); }
        return nc;
      });
      spawnParticles(tile.id, true);
      setTiles(ts => ts.map(t => t.id===tile.id ? {...t,state:"correct"} : t));
      setTimeout(()=>setTiles(ts=>ts.map(t=>t.id===tile.id&&t.state==="correct"?{...t,state:"cleared"}:t)), 420);
    } else {
      sfx.wrong();
      setCombo(0);
      setMomentum(m => { const nm=Math.max(0,m-35); if(nm===0) setNinja(false); return nm; });
      setNinja(false);
      setShake(true); setTimeout(()=>setShake(false), 460);
      spawnParticles(tile.id, false);
      setTiles(ts => ts.map(t => t.id===tile.id ? {...t,state:"wrong"} : t));
      setTimeout(()=>setTiles(ts=>ts.map(t=>t.id===tile.id&&t.state==="wrong"?{...t,state:"cleared"}:t)), 520);
    }
  };

  if (screen==="menu")   return <MenuScreen onJourney={()=>startStage(0,true)} onChooseStage={()=>setScreen("stages")}/>;
  if (screen==="stages") return <StageSelect onSelect={sid=>startStage(sid,false)} onBack={()=>setScreen("menu")}/>;
  if (screen==="score")  return (
    <ScoreScreen
      score={score} maxCombo={maxCombo} round={round} stageId={stageId} journeyMode={journey}
      onRestart={()=>startStage(stageId,journey)}
      onNext={()=>startStage(Math.min(stageId+1,STAGES.length-1),true)}
      onMenu={()=>setScreen("menu")}
    />
  );

  return (
    <div ref={arenaR} style={{
      position:"relative", width:"100%", height:"100vh", overflow:"hidden",
      background:ninja
        ? "radial-gradient(ellipse at 50% 0%,#001a2e 0%,#000d1a 55%,#000008 100%)"
        : "radial-gradient(ellipse at 50% 0%,#1a0a2e 0%,#0a0614 55%,#020008 100%)",
      transition:"background 0.6s",
      animation:shake?"screenShake 0.45s ease":"none",
    }}>
      <style dangerouslySetInnerHTML={{__html:GCSS}}/>
      <StarField/>

      {ninja && (
        <div style={{position:"absolute",inset:0,pointerEvents:"none",zIndex:1,background:"radial-gradient(ellipse 70% 50% at 50% 50%,rgba(0,255,238,0.04) 0%,transparent 70%)",animation:"ninjaPulse 1s ease-in-out infinite"}}/>
      )}

      <HUD
        score={score} combo={combo}
        stageName={stage.name} stageAccent={stage.accent}
        challNum={(challIdx%stage.challenges.length)+1} total={stage.challenges.length}
        timeLeft={timeLeft} noTimer={noTimer}
        ninjaMode={ninja} comboTier={comboTier}
      />
      <MomentumBar momentum={momentum} ninjaMode={ninja}/>

      <div style={{position:"absolute",top:80,left:"50%",transform:"translateX(-50%)",textAlign:"center",zIndex:20,pointerEvents:"none",maxWidth:580,padding:"0 20px"}}>
        <div style={{fontSize:9,letterSpacing:4,color:"#444",textTransform:"uppercase",fontFamily:'"Rajdhani",sans-serif',marginBottom:5}}>
          FIND AND SLASH
        </div>
        <div style={{
          fontSize:stage.hint>=2?17:15, fontWeight:700, letterSpacing:2,
          color:ninja?"#00ffee":"#ffd700",
          textShadow:ninja?"0 0 20px #00ffee":"0 0 14px rgba(255,215,0,0.4)",
          fontFamily:'"Cinzel",serif', lineHeight:1.35, transition:"all 0.4s",
        }}>
          {chall ? chall.label.toUpperCase() : ""}
        </div>
      </div>

      {stage.hint>0 && (
        <div style={{position:"absolute",bottom:58,left:"50%",transform:"translateX(-50%)",zIndex:30,background:"rgba(255,215,0,0.07)",outline:"1px solid rgba(255,215,0,0.18)",border:"none",borderRadius:20,padding:"5px 14px",fontSize:9,color:"rgba(255,215,0,0.6)",letterSpacing:2,fontFamily:'"Rajdhani",sans-serif',whiteSpace:"nowrap"}}>
          {stage.hint>=3 ? "correct tiles glow gold" : stage.hint>=2 ? "watch for the subtle glow" : "hint active"}
        </div>
      )}

      <div ref={gridR} style={{
        position:"absolute", top:"50%", left:"50%",
        transform:"translate(-50%,-50%) translateY(18px)",
        display:"grid", gridTemplateColumns:"repeat(5, 90px)",
        gap:8, zIndex:10,
        filter:trans?"blur(3px) brightness(0.5)":"none",
        transition:"filter 0.4s",
      }}>
        {tiles.map(tile => (
          <Tile key={tile.id} tile={tile} ninjaMode={ninja} hintLevel={stage.hint} onClick={()=>handleTile(tile)}/>
        ))}
      </div>

      <ParticleLayer particles={parts}/>
      {banner && <Banner text={banner.text} color={banner.color}/>}
    </div>
  );
}
