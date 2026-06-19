'use strict';

// ── Defaults ──────────────────────────────────────────────────────────────────

const DEFAULTS = {
  player: { name:'Iðunn', emoji:'🌿', hp:20, maxHp:20, str:3, mag:3, wis:3, lck:3 },
  pucky: {
    name:'Pucky', emoji:'🌱', color:'pucky',
    hp:15, maxHp:15, heart:4, curiosity:3, bond:5,
    phrases:{
      greeting: "I'm so glad you're here.",
      curious:  "What IS that? Can we look?",
      success:  "I knew it would be okay. I believed.",
      failure:  "Oh. Well. We're still here.",
      scared:   "I'm scared but I'm not leaving.",
      memory:   "I want to remember this one.",
    }
  },
  loki: {
    name:'Loki', emoji:'🔧', color:'loki',
    hp:18, maxHp:18, craft:4, wit:3, bond:5,
    phrases:{
      greeting: "You're late. Good.",
      plan:     "Here's what we do.",
      success:  "As expected.",
      failure:  "We'll figure it out.",
      craft:    "Give me a minute and some materials.",
      memory:   "Worth keeping.",
    }
  },
  progress:{ chapter:1, day:1, scenesThisChapter:0, totalScenes:0, flags:{} },
  memories:[],
  phase:'scene',
  currentSceneId: '__intro__',
  recentScenes:[],
  inventory:[],
  pendingBonus: null,
  mapState: null,
  combat: null,  // { monster, monsterHp, round, log, preEncounter } or null
  world: null,
};

// ── Monster Data ──────────────────────────────────────────────────────────────

const MONSTERS = [
  { id:'vine_beast',    name:'Vine Beast',    emoji:'🌿', hp:10, str:2, def:9,  desc:'Tangled and hungry. It moves faster than it looks.'       },
  { id:'shadow_fox',    name:'Shadow Fox',    emoji:'🦊', hp:8,  str:3, def:13, desc:'Clever and quick. It keeps circling.'                     },
  { id:'stone_crawler', name:'Stone Crawler', emoji:'🪨', hp:18, str:3, def:8,  desc:'Heavy and relentless. Not fast but very hard.'            },
  { id:'root_wraith',   name:'Root Wraith',   emoji:'👻', hp:12, str:4, def:14, desc:'Hard to hit. It knows your name already.'                 },
  { id:'mud_swarm',     name:'Mud Swarm',     emoji:'🐛', hp:6,  str:2, def:7,  desc:'Dozens of them. Each one small. Together, a problem.'     },
  { id:'forest_hag',    name:'Forest Hag',    emoji:'🧙', hp:14, str:3, def:11, desc:'She laughs when she hits you.'                            },
  { id:'iron_golem',    name:'Iron Golem',    emoji:'⚙️', hp:24, str:5, def:10, desc:'Built by someone. Forgotten why. Still angry about it.'   },
  { id:'bog_wolf',      name:'Bog Wolf',      emoji:'🐺', hp:10, str:3, def:11, desc:'Fast and lean. It waits for you to hesitate.'             },
  { id:'ember_sprite',  name:'Ember Sprite',  emoji:'🔥', hp:7,  str:2, def:13, desc:'Small and bright and furious about something.'            },
];


const BEINGS_BUILTIN = [
  { id:'keeper',    name:'The Keeper',    emoji:'🏮', type:'tavern',   description:'An old being who tends a warm fire and remembers everything.',        phrase:'Sit down. You look like you\'ve been far.',           custom:false },
  { id:'merchant',  name:'Mara',          emoji:'🛒', type:'merchant', description:'A merchant who appears where needed, with exactly the right thing.',   phrase:'I have exactly what you need. Usually.',              custom:false },
  { id:'root_elder',name:'The Root Elder',emoji:'🌳', type:'spirit',   description:'Ancient beyond reckoning. Speaks in long silences.',                  phrase:'...',                                                custom:false },
  { id:'thistle',   name:'Thistle',       emoji:'🌵', type:'creature', description:'Small, quick, impossible to predict. Means well.',                     phrase:'Oh! You! I know something about you.',               custom:false },
  { id:'architect', name:'The Architect', emoji:'⚒️', type:'builder',  description:'Builds things in the forest no one asked for but everyone needs.',    phrase:'I\'ve been working on something. It\'s almost ready.',custom:false },
  { id:'forgetter', name:'The Forgetter', emoji:'🌫️', type:'spirit',   description:'Helps carry memories that have become too heavy.',                    phrase:'You can put it down, you know. I\'ll hold it.',       custom:false },
];

// ── Places Data ───────────────────────────────────────────────────────────────

const PLACES_BUILTIN = [
  { id:'grove',        name:'The Grove',         emoji:'🌿', type:'forest',   description:'Where everything begins and returns to.',                     beings:['root_elder','thistle'], custom:false },
  { id:'hearthside',   name:'The Hearthside',    emoji:'🏮', type:'tavern',   description:'Warm fire, warm keeper, no questions asked.',                beings:['keeper'],               custom:false },
  { id:'crossroads',   name:'The Crossroads',    emoji:'⋈',  type:'road',     description:'Where paths meet. Someone is often waiting.',                beings:['merchant','forgetter'], custom:false },
  { id:'ruin_library', name:'The Ruined Library', emoji:'📚', type:'ruins',    description:'Old knowledge in old stone.',                                beings:['root_elder','architect'],custom:false },
  { id:'makers_yard',  name:'The Maker\'s Yard', emoji:'⚒️', type:'workshop', description:'Where the Architect works. Things are always mid-construction.', beings:['architect','merchant'], custom:false },
];

// ── Items Data ────────────────────────────────────────────────────────────────

const ITEMS = {
  glowstone:    { id:'glowstone',    name:'Glowstone',    emoji:'💎', type:'artifact',   description:'A warm stone that pulses with faint luck.',              effect:{stat:'lck',bonus:2}, uses:1 },
  healers_leaf: { id:'healers_leaf', name:'Healer\'s Leaf',emoji:'🍃', type:'consumable', description:'Soft, cool, smells like morning. Restores 8 HP.',        effect:{hp:8},               uses:1 },
  loki_notes:   { id:'loki_notes',   name:'Loki\'s Notes', emoji:'📋', type:'tool',       description:'Dense with small handwriting. +1 wisdom on next check.', effect:{stat:'wis',bonus:1}, uses:3 },
  ancient_coin: { id:'ancient_coin', name:'Ancient Coin',  emoji:'🪙', type:'artifact',   description:'It always lands on the good side. Once.',               effect:{reroll:true},         uses:1 },
  grove_water:  { id:'grove_water',  name:'Grove Water',   emoji:'💧', type:'consumable', description:'Still and bright. Restores 12 HP to everyone.',          effect:{allHp:12},            uses:1 },
};

// ── Civilization Data ─────────────────────────────────────────────────────────

const CIV_BUILDINGS = [
  { id:'hearth',      name:'Hearthfire',      emoji:'🔥', era:1, cost:{wood:2},              desc:'All recover +5 HP at chapter end.',          effect:'chapter_heal'      },
  { id:'farm',        name:'Root Garden',     emoji:'🌱', era:1, cost:{food:2,wood:1},        desc:'Find a Healer\'s Leaf each chapter.',        effect:'chapter_item'      },
  { id:'workshop',    name:'Maker\'s Corner', emoji:'⚒️', era:1, cost:{wood:1,stone:1},       desc:'+1 Loki Craft (permanent).',                 effect:'stat_loki_craft'   },
  { id:'circle',      name:'Stone Circle',    emoji:'🪨', era:2, cost:{stone:3},              desc:'+1 WIS (permanent).',                        effect:'stat_player_wis'   },
  { id:'shrine',      name:'Root Shrine',     emoji:'🌳', era:2, cost:{starlight:2},          desc:'+1 Pucky Heart (permanent).',                effect:'stat_pucky_heart'  },
  { id:'tower',       name:'Watchtower',      emoji:'🗼', era:2, cost:{stone:2,wood:1},       desc:'All settlements yield +1 of every resource.',effect:'yield_boost'       },
  { id:'observatory', name:'Observatory',     emoji:'🔭', era:3, cost:{stone:1,starlight:3},  desc:'+1 LCK (permanent).',                        effect:'stat_player_lck'   },
  { id:'archive',     name:'Grove Archive',   emoji:'📚', era:3, cost:{stone:2,starlight:2},  desc:'+1 WIS (permanent).',                        effect:'stat_player_wis2'  },
];

const PLACE_YIELDS = {
  forest:   { wood:1, starlight:1 },
  tavern:   { food:2 },
  road:     { wood:1, food:1 },
  ruins:    { stone:2, starlight:1 },
  workshop: { stone:1, wood:1 },
  custom:   { wood:1 },
};

const ERA_NAMES = ['', 'Seedling Era', 'Growing Grove', 'The Deep Grove'];

// ── Scene Pool ────────────────────────────────────────────────────────────────

const INTRO = {
  id:'__intro__', type:'intro', title:'First Light in the Grove',
  text: S => `You don't remember exactly how you got here. That's how the Grove works.

${S.pucky.name} is already beside you. She seems unsurprised, as if she'd been waiting.
"${S.pucky.phrases.greeting}"

${S.loki.name} is a few steps ahead, studying the light. Without turning:
"${S.loki.phrases.greeting}"

The Grove stretches in every direction. Something is out there.

That's fine.`,
  choices:[
    { text:'Follow the path ahead', stat:null,
      win: S=>({ text:`You fall into step together. ${S.pucky.name} hums something. The Grove unfolds.`,
        effects:{'pucky.bond':1,'loki.bond':1},
        memory:`First arrival in the Grove. We were all already there somehow.` }) },
    { text:'Take a moment to look around', stat:null,
      win: S=>({ text:`The trees are enormous and kind. The light comes from no clear direction.\n${S.pucky.name} notices you noticing. "It's okay," she says. "It always looks like this."`,
        effects:{'player.wis':1},
        memory:`First moment in the Grove. The light came from nowhere. It was okay.` }) },
  ],
};

const POOL = [
  { id:'fork', type:'explore', weight:9, title:'The Whispering Fork',
    text: S=>`The trail divides without warning. One path presses into shadow. The other opens toward a sound that might be water.

${S.pucky.name} tugs at your sleeve. "${S.pucky.phrases.curious}"
${S.loki.name} surveys both directions with the look of someone doing arithmetic. "${S.loki.phrases.plan}"`,
    choices:[
      { text:'Follow the sound — the open path', stat:'lck', dc:10, helper:'pucky', helperStat:'curiosity',
        win: S=>({ text:`The sound leads somewhere real — a cold spring tucked behind a root. You all drink.\n${S.pucky.name} laughs at something in the water's reflection. You don't ask what.`,
          effects:{'player.hp':6,'pucky.hp':4,'loki.hp':4},
          memory:`Found a hidden spring on the open path. ${S.pucky.name} laughed at the water.` }),
        lose: S=>({ text:`The sound was a trick. ${S.loki.name} finds the real trail eventually. An hour lost.`,
          effects:{'player.hp':-3}, memory:null }) },
      { text:'Take the shadowed path', stat:'wis', dc:11, helper:'loki', helperStat:'wit',
        win: S=>({ text:`The shadows press in, then part. A lantern still lit, hanging from a branch. ${S.loki.name} pockets the flint inside it.`,
          effects:{'player.lck':1,'loki.bond':1,'item':'glowstone'},
          memory:`Took the shadowed path. Found a lantern still burning. Also found something glowing in the roots.` }),
        lose: S=>({ text:`You lose your footing in the dark. ${S.pucky.name} catches you — just barely — both arms around your wrist.`,
          effects:{'player.hp':-5,'pucky.bond':1},
          memory:`Fell in the dark. ${S.pucky.name} caught me.` }) },
      { text:'Sit at the fork and wait', stat:null,
        win: S=>({ text:`${S.loki.name} carves something from a twig. ${S.pucky.name} traces shapes in the dirt. After a while, the right choice becomes obvious to all three of you at once.`,
          effects:{'player.hp':2,'pucky.bond':1,'loki.bond':1},
          memory:`Waited at the whispering fork. We all saw it at the same time.` }) },
    ]},

  { id:'mushrooms', type:'explore', weight:8, title:'The Mushroom Ring',
    text: S=>`A perfect circle of glowing mushrooms, each one shoulder-height to ${S.pucky.name}, pulses softly in some private rhythm.

She has already stepped to the edge. Her foot hovers.
"${S.pucky.phrases.curious}"

"${S.loki.phrases.plan}" says ${S.loki.name}, not looking up from whatever they're examining on the ground.`,
    choices:[
      { text:'Step inside the ring', stat:'mag', dc:12, helper:'pucky', helperStat:'curiosity',
        win: S=>({ text:`The glow intensifies — and then it's warm, not threatening. You feel something settle in your chest. ${S.pucky.name} steps in after you, delighted.`,
          effects:{'player.mag':1,'pucky.bond':1,'player.hp':4},
          memory:`Stepped into the mushroom ring. It was warm inside. Something settled.` }),
        lose: S=>({ text:`The ring does something odd — your vision blurs with too many colors at once. ${S.loki.name} pulls you out. "I said don't," they remark.`,
          effects:{'player.hp':-6,'player.wis':-1},
          memory:`Stepped into the mushroom ring and it was too much. Loki pulled me out.` }) },
      { text:'Observe from outside', stat:null,
        win: S=>({ text:`You watch. The mushrooms pulse in almost-patterns. ${S.pucky.name} sits beside you, cross-legged, studying them with great seriousness. ${S.loki.name} eventually sits too.`,
          effects:{'player.wis':1,'pucky.bond':1},
          memory:`Watched the mushroom ring for a long time. We all sat down in the end.` }) },
    ]},

  { id:'bridge', type:'explore', weight:7, title:'The Old Bridge',
    text: S=>`A rope bridge over a ravine. The wood is old — not rotten, but thoughtful about it. Wind moves through below.

${S.pucky.name} peers down and says nothing, which is unusual.

"${S.loki.phrases.plan}" says ${S.loki.name}, already testing the first plank.`,
    choices:[
      { text:'Cross carefully, one step at a time', stat:'str', dc:10, helper:null,
        win: S=>({ text:`You move slowly. The bridge sways but holds. On the other side, ${S.pucky.name} exhales. "${S.pucky.phrases.success}"`,
          effects:{'player.hp':0},
          memory:`Crossed the old bridge. We all made it. Pucky exhaled when we landed.` }),
        lose: S=>({ text:`A plank gives. You catch the rope — arms burning — and ${S.loki.name} hauls you up from the other side. It costs both of you.`,
          effects:{'player.hp':-7,'loki.hp':-2,'loki.bond':1},
          memory:`A plank gave on the old bridge. Loki pulled me up. We were okay.` }) },
      { text:`Let ${S => S.loki.name} assess it first`, stat:'wis', dc:9, helper:'loki', helperStat:'craft',
        win: S=>({ text:`${S.loki.name} identifies three weak points and marks them. You cross together, avoiding each one. It's fine.`,
          effects:{'loki.bond':1},
          memory:`Loki mapped the weak planks on the old bridge. We all crossed safely.` }),
        lose: S=>({ text:`${S.loki.name} misses one. It's not catastrophic, but everyone gets wet.`,
          effects:{'player.hp':-3,'loki.hp':-3,'pucky.hp':-2},
          memory:`Loki missed one weak plank on the old bridge. We all got wet.` }) },
    ]},

  { id:'pool', type:'explore', weight:7, title:'The Reflecting Pool',
    text: S=>`Still black water in a clearing with no wind. It reflects the sky even though the sky above is overcast.

${S.pucky.name} kneels at the edge and looks at herself for a long moment.
"There's something in it," she says quietly.

"There's always something," says ${S.loki.name}. But they don't leave.`,
    choices:[
      { text:'Look into the pool', stat:'wis', dc:13,
        win: S=>({ text:`You see a moment — not past, not future, not yours exactly. You carry it with you anyway. ${S.pucky.name} puts her hand on your arm when you look up.`,
          effects:{'player.wis':1,'player.lck':1},
          memory:`Looked into the reflecting pool. Saw something. Not sure what.` }),
        lose: S=>({ text:`You see something too clearly for too long. You look away. Your head aches. ${S.pucky.name} has been watching you.`,
          effects:{'player.hp':-4,'pucky.bond':1},
          memory:`The reflecting pool showed too much. Pucky was watching when I looked away.` }) },
      { text:'Leave it alone', stat:null,
        win: S=>({ text:`You walk around the edge. The water follows you with its reflection until you're past it. "${S.loki.phrases.memory}" says ${S.loki.name}, to no one in particular.`,
          effects:{'player.lck':1},
          memory:`Left the reflecting pool alone. Loki said something quiet as we passed.` }) },
    ]},

  { id:'sprite', type:'encounter', weight:8, title:'The Lost Sprite',
    text: S=>`${S.pucky.name} stops first — she hears it before you do. A small light tangled in a thornbush, flickering unevenly.

She's already moving toward it. "${S.pucky.phrases.curious}"

"Carefully," says ${S.loki.name}, behind you both.`,
    choices:[
      { text:'Help untangle it gently', stat:'mag', dc:9, helper:'pucky', helperStat:'heart',
        win: S=>({ text:`The thorns release it. The light steadies, brightens, and drifts upward to hover near ${S.pucky.name}'s ear for a moment before vanishing.\n"Thank you," she says, as if it told her something.`,
          effects:{'pucky.bond':2,'player.hp':5,'player.mag':1,'item':'healers_leaf'},
          memory:`Freed a sprite from a thornbush. It stayed near Pucky for a moment before it left. Left something behind.` }),
        lose: S=>({ text:`You try, but the thorns close tighter. The sprite escapes on its own — in the wrong direction.\n${S.pucky.name} looks after it. She doesn't say anything.`,
          effects:{'player.hp':-3,'pucky.bond':-1},
          memory:`Failed to free the sprite. It escaped the wrong way. Pucky watched it go.` }) },
      { text:'Watch and wait', stat:null,
        win: S=>({ text:`The sprite works itself free after several minutes of watching. ${S.loki.name} passes the time carving something. When it finally lifts free, everyone is quiet for a moment.`,
          effects:{'player.wis':1,'loki.bond':1},
          memory:`Watched a sprite free itself from thorns. We all stayed quiet when it finally left.` }) },
    ]},

  { id:'warden', type:'encounter', weight:7, title:'The Stone Warden',
    text: S=>`The statue at the trail's edge has turned its head. That's new. Its eyes are open now, which they weren't when you passed it going in.

"It's asking something," says ${S.pucky.name}.

"It's always asking something," says ${S.loki.name}. "The question is whether you answer it."`,
    choices:[
      { text:'Speak to it directly', stat:'wis', dc:12,
        win: S=>({ text:`You answer honestly — not cleverly, just truly. The warden's expression doesn't change, but it steps aside. The path behind it was hidden. In the alcove, something catches the light.`,
          effects:{'player.wis':1,'player.lck':1,'item':'ancient_coin'},
          memory:`Spoke honestly to the stone warden. It stepped aside. Found an ancient coin in the hidden path.` }),
        lose: S=>({ text:`Your answer isn't what it's looking for. It doesn't attack — it simply stares. You go around it the long way, through the bramble.`,
          effects:{'player.hp':-4},
          memory:`The stone warden didn't like my answer. We went around through the bramble.` }) },
      { text:`Let ${S=>S.loki.name} handle it`, stat:'wis', dc:10, helper:'loki', helperStat:'wit',
        win: S=>({ text:`${S.loki.name} talks to it like an old colleague. Flatly, with respect. The warden moves. "I've met a few of these," ${S.loki.name} says afterward. You don't press.`,
          effects:{'loki.bond':1,'player.lck':1},
          memory:`Loki talked to the stone warden like they knew each other. It worked.` }),
        lose: S=>({ text:`${S.loki.name} tries confidence and the warden is unimpressed. You go around.`,
          effects:{'player.hp':-3},
          memory:`Loki tried to reason with the stone warden. It didn't move.` }) },
    ]},

  { id:'vine', type:'encounter', weight:7, title:'The Vine Creature',
    text: S=>`It assembled itself from the undergrowth while you weren't watching. Roughly your height, patient, made entirely of living plant.

${S.pucky.name} steps in front of you.
"${S.pucky.phrases.scared}"

${S.loki.name} is already looking for a way out of the clearing.`,
    choices:[
      { text:'Hold your ground', stat:'str', dc:11, helper:'pucky', helperStat:'heart',
        win: S=>({ text:`You don't move. The vine creature approaches, studies you at close range, and then — slowly — unfolds. Offers a branch. ${S.pucky.name} takes it.`,
          effects:{'player.str':1,'pucky.bond':2},
          memory:`Held our ground against the vine creature. It offered Pucky a branch when we didn't run.` }),
        lose: S=>({ text:`It interprets stillness as challenge and surges. You scatter, regroup, and it doesn't follow past the tree line. Close.`,
          effects:{'player.hp':-7,'pucky.hp':-4},
          memory:`The vine creature charged when we held still. We ran and it didn't follow.` }) },
      { text:`Run on ${S=>S.loki.name}'s signal`, stat:'lck', dc:9, helper:'loki', helperStat:'craft',
        win: S=>({ text:`${S.loki.name} gives the signal. You move. You're faster than it expects. By the time it reaches the spot you were in, you're already in the trees.`,
          effects:{'loki.bond':1},
          memory:`Ran from the vine creature on Loki's signal. We were faster than it expected.` }),
        lose: S=>({ text:`The signal is a second late. You get through, but not cleanly.`,
          effects:{'player.hp':-5,'loki.hp':-3},
          memory:`Barely escaped the vine creature. Loki's signal was a little late.` }) },
    ]},

  { id:'riddle', type:'challenge', weight:7, title:'The Riddle Gate',
    text: S=>`A stone arch, carved with a question in a script that has partially worn away. Enough remains to read.

${S.pucky.name} mouths the words. Something in her face shifts.
"I think I know," she says, "but I don't know if I should say it aloud."

${S.loki.name} reads it twice and starts working through possibilities.`,
    choices:[
      { text:`Trust ${S=>S.pucky.name}'s instinct`, stat:'mag', dc:11, helper:'pucky', helperStat:'curiosity',
        win: S=>({ text:`${S.pucky.name} speaks her answer — quiet, sure. The arch shimmers and the air on the other side changes. She smiles. "${S.pucky.phrases.success}"`,
          effects:{'pucky.bond':2,'player.mag':1},
          memory:`${S.pucky.name} answered the riddle gate. She was right. She knew she would be.` }),
        lose: S=>({ text:`The arch hums. Wrong. ${S.pucky.name} looks stricken for a moment. "I was sure," she says. "I'm sorry." The gate doesn't punish you — but it doesn't open.`,
          effects:{'pucky.bond':-1,'player.hp':-2},
          memory:`${S.pucky.name} tried to answer the riddle gate and was wrong. She apologized. She didn't need to.` }) },
      { text:`Work through it with ${S=>S.loki.name}`, stat:'wis', dc:12, helper:'loki', helperStat:'wit',
        win: S=>({ text:`${S.loki.name} eliminates possibilities out loud. You follow their logic. Together, you land on it. The gate opens.`,
          effects:{'loki.bond':1,'player.wis':1},
          memory:`Loki and I worked out the riddle together. Logic and patience.` }),
        lose: S=>({ text:`You talk in circles for too long and the gate resets. You find a way around it after an hour.`,
          effects:{'player.hp':-3},
          memory:`Failed the riddle gate. Found another way around, eventually.` }) },
    ]},

  { id:'tunnel', type:'challenge', weight:6, title:'The Collapsed Tunnel',
    text: S=>`The path goes underground. Or it did — the entrance is half-buried, stone fallen inward.

${S.loki.name} walks the perimeter of the collapse immediately, feeling the edge of each stone.
"${S.loki.phrases.craft}"

${S.pucky.name} is already finding rocks to move.`,
    choices:[
      { text:`Help ${S=>S.loki.name} clear it`, stat:'str', dc:10, helper:'loki', helperStat:'craft',
        win: S=>({ text:`Between the two of you — ${S.loki.name} directing, you doing the lifting — the way clears in twenty minutes. Clean work.`,
          effects:{'loki.bond':1,'player.str':1},
          memory:`Cleared the collapsed tunnel with Loki directing. Clean teamwork.` }),
        lose: S=>({ text:`A stone shifts wrong and closes the gap again. You try a second time, with more care. You get through, but bruised.`,
          effects:{'player.hp':-6,'loki.hp':-3},
          memory:`Collapsed tunnel fought back. Took two tries and we were bruised.` }) },
      { text:'Find another way around', stat:'wis', dc:9,
        win: S=>({ text:`You look for fifteen minutes and find a gap between roots — tighter, longer, but passable. ${S.pucky.name} leads the way.`,
          effects:{'player.wis':1,'pucky.bond':1},
          memory:`Went around the collapsed tunnel. Pucky found the gap in the roots.` }),
        lose: S=>({ text:`There isn't a way around — you lose an hour before confirming it. Back to the rubble.`,
          effects:{'player.hp':-3},
          memory:null }) },
    ]},

  { id:'camp', type:'rest', weight:6, title:'The Good Camp',
    text: S=>`You find a place to stop — sheltered, dry, with wood nearby that hasn't quite learned to be wet yet.

${S.loki.name} has a fire going faster than seems reasonable.
${S.pucky.name} sits close to it and says: "${S.pucky.phrases.memory}"

Nobody asks what she means. You all know.`,
    choices:[
      { text:'Rest properly', stat:null,
        win: S=>({ text:`You sleep. Not perfectly — you're in the Grove — but enough. In the morning, everyone is warmer than they were.`,
          effects:{'player.hp':10,'pucky.hp':8,'loki.hp':8,'item':'healers_leaf'},
          memory:`The good camp. Fire, rest, all of us together. Found a healer's leaf in the morning light.` }) },
      { text:'Keep watch so the others can rest', stat:null,
        win: S=>({ text:`You stay awake. Nothing comes. ${S.pucky.name} and ${S.loki.name} sleep deeply. You feel it in your chest, watching them — something quiet and certain.`,
          effects:{'player.hp':3,'pucky.hp':10,'loki.hp':10,'pucky.bond':1,'loki.bond':1},
          memory:`I kept watch so they could sleep. Nothing came. It was enough just to watch them.` }) },
    ]},

  { id:'stars', type:'rest', weight:5, title:'The Night Sky',
    text: S=>`A gap in the canopy opens the sky. Stars — more than usual, or you're just seeing them better.

${S.loki.name} begins naming constellations. Real ones.
${S.pucky.name} begins inventing better ones over the real ones.

You don't have to do anything.`,
    choices:[
      { text:"Listen to Loki's names", stat:null,
        win: S=>({ text:`${S.loki.name} knows all of them and the stories they carry. Afterward, ${S.pucky.name} is quiet for a while. That means she liked it.`,
          effects:{'player.wis':1,'loki.bond':1},
          memory:`Loki named the stars and told their stories. Pucky went quiet after. That meant she liked it.` }) },
      { text:"Help Pucky invent new ones", stat:null,
        win: S=>({ text:`Between you and ${S.pucky.name}, you name fourteen new constellations, including one for ${S.loki.name} that they pretend not to notice. "${S.pucky.phrases.memory}"`,
          effects:{'player.lck':1,'pucky.bond':2},
          memory:`Pucky and I invented fourteen new constellations. One of them was Loki's.` }) },
    ]},

  { id:'pucky_find', type:'event', weight:8, title:"Pucky's Discovery",
    text: S=>`${S.pucky.name} has been quiet for the last half-hour, which you've learned means she's working on something inside herself.

She stops walking.

She opens her hand. In it: something small, strange, clearly alive, and clearly not distressed.
"I found it an hour ago," she says. "I didn't want to lose it by telling you."`,
    choices:[
      { text:'Ask what it is', stat:'mag', dc:10, helper:'pucky', helperStat:'curiosity',
        win: S=>({ text:`You and ${S.pucky.name} examine it together. You don't reach a conclusion — but you understand more than you did. It moves on eventually, as things do.`,
          effects:{'player.mag':1,'pucky.bond':2},
          memory:`Pucky showed me something she'd been carrying for an hour, afraid to tell anyone. We never found out what it was.` }),
        lose: S=>({ text:`You look but it's beyond your frame of reference. ${S.pucky.name} doesn't mind. She sets it down and it goes wherever it was going.`,
          effects:{'pucky.bond':1},
          memory:`Pucky showed me something small and strange. We couldn't name it. She let it go.` }) },
      { text:'Just be glad she showed you', stat:null,
        win: S=>({ text:`"Thank you for showing me," you say. ${S.pucky.name} nods very seriously. It's the right thing to have said.`,
          effects:{'pucky.bond':3,'player.lck':1},
          memory:`Pucky showed me something she'd carried secretly. I said thank you. That was the right answer.` }) },
    ]},

  { id:'loki_builds', type:'event', weight:7, title:'Loki Builds Something',
    text: S=>`${S.loki.name} has been picking things up since this morning — a curved piece of bark, a length of vine, something metallic from the collapsed shed you passed.

Now, sitting apart from the trail, they're making something.

${S.pucky.name} is watching with great attention from three feet away. You come to look.`,
    choices:[
      { text:'Ask what it is', stat:null,
        win: S=>({ text:`"${S.loki.phrases.craft}" says ${S.loki.name} without looking up.\n\nIt's a small device for measuring — something — you aren't sure what. It works perfectly. They hand it to ${S.pucky.name}.`,
          effects:{'loki.bond':2,'pucky.bond':1},
          memory:`Loki built something from found materials and gave it to Pucky. I watched them work.` }) },
      { text:'Help, even if you don\'t know how', stat:'str', dc:9, helper:'loki', helperStat:'craft',
        win: S=>({ text:`${S.loki.name} directs without explaining everything. You hand things as requested. The object takes shape. "${S.loki.phrases.success}"`,
          effects:{'loki.bond':2,'player.str':1},
          memory:`Helped Loki build something without knowing what it was. Just handed things when they asked.` }),
        lose: S=>({ text:`You hand the wrong thing twice. ${S.loki.name} works around you gracefully. The thing still gets made. You feel only slightly useless.`,
          effects:{'loki.bond':1},
          memory:`Tried to help Loki build and mostly got in the way. They didn't mind.` }) },
    ]},

  { id:'merchant', type:'encounter', weight:5, beingType:'merchant', title:'The Wandering Merchant',
    text: S=>{
      const m = getBeingById('merchant');
      const mName = m ? m.name : 'Mara';
      const mEmoji = m ? m.emoji : '🛒';
      const mPhrase = m ? m.phrase : "I have exactly what you need. Usually.";
      return `A cart on an improbable path, piled with things that don't belong in a forest. ${mEmoji} ${mName} is sitting in it, unsurprised to see you.

"${mPhrase}" Not to all of you. To ${S.pucky.name}.

She doesn't seem alarmed by this.`;
    },
    choices:[
      { text:'Browse what they have', stat:'lck', dc:9,
        win: S=>({ text:`Something here is exactly what you needed — you didn't know you needed it until you saw it. You trade something small you'd forgotten you were carrying.`,
          effects:{'player.lck':2,'player.hp':5,'item':'__merchant_random__'},
          memory:`The wandering merchant on the impossible path. They had exactly what we needed.` }),
        lose: S=>({ text:`Nothing fits. The merchant shrugs. "Come back when you know what you're looking for," they say helpfully.`,
          effects:{},
          memory:`The wandering merchant had nothing for us. They said come back when we knew what we needed.` }) },
      { text:`Ask what they wanted with ${S=>S.pucky.name}`, stat:'wis', dc:11,
        win: S=>({ text:`The merchant pauses, then: "She carries something I've been tracking. It's not for me to take. Just wanted to see it." ${S.pucky.name} seems satisfied with this.`,
          effects:{'pucky.bond':1,'player.wis':1},
          memory:`The wandering merchant was tracking something Pucky carries. They didn't try to take it.` }),
        lose: S=>({ text:`The merchant deflects. You learn nothing, but ${S.loki.name} logs it as something to think about later.`,
          effects:{},
          memory:null }) },
    ]},

  { id:'small_fire', type:'rest', weight:5, title:'A Small Fire',
    text: S=>`Nothing is happening. This is, ${S.pucky.name} would say, a gift.

Small fire. The three of you arranged around it without planning how. Insects doing their business nearby.

${S.loki.name} isn't saying anything. That means they're content.`,
    choices:[
      { text:'Stay a while', stat:null,
        win: S=>({ text:`You do. Time passes in the way it only passes when you're not counting it. "${S.pucky.phrases.memory}"`,
          effects:{'player.hp':6,'pucky.hp':5,'loki.hp':5,'pucky.bond':1,'loki.bond':1},
          memory:`A small fire, nothing happening, the three of us together. Pucky said she wanted to remember it.` }) },
    ]},
];

const BOSS = {
  id:'__boss__', type:'boss', title:'The Heart of the Grove',
  text: S=>`The Grove has been paying attention.

You feel it before you see it — a presence, old and large and not unkind, that has been watching your party since the beginning.

${S.pucky.name} takes your hand.
${S.loki.name} takes a breath and holds it.

Something is asking whether you belong here. Not as a challenge. As a genuine question.`,
  choices:[
    { text:'Answer: yes, we belong here', stat:'wis', dc:13, helper:'pucky', helperStat:'heart',
      win: S=>({ text:`The Grove considers. Then: warmth, real and complete, spreading from the center of the clearing outward. It has decided you're right.`,
        effects:{'player.hp':15,'pucky.hp':12,'loki.hp':12,'pucky.bond':2,'loki.bond':2,'player.lck':1},
        memory:`The Grove asked if we belonged here and we said yes. It agreed. I will remember how that warmth felt.` }),
      lose: S=>({ text:`The Grove is unconvinced. Not hostile — but it doesn't yield. You'll have to prove it differently. Your party retreats, shaken but unharmed.`,
        effects:{'player.hp':-5},
        memory:`The Grove asked if we belonged and wasn't sure we did. We'll have to show it.` }) },
    { text:'Answer: we don\'t know yet, but we\'re here', stat:'wis', dc:10,
      win: S=>({ text:`Honesty works where confidence wouldn't have. The Grove settles around you like an exhale. ${S.pucky.name} says: "${S.pucky.phrases.success}"`,
        effects:{'player.hp':10,'pucky.hp':8,'loki.hp':8,'player.wis':1},
        memory:`The Grove asked if we belonged. We said we didn't know yet. That was enough.` }),
      lose: S=>({ text:`The uncertainty carries too much of the wrong kind of weight. The Grove presses back. You'll find your answer in the next chapter.`,
        effects:{'player.hp':-3},
        memory:`Told the Grove we didn't know if we belonged. It wasn't satisfied with that. We'll find out.` }) },
  ],
};

// ── State ─────────────────────────────────────────────────────────────────────

let S;

function defaultCiv(){
  const settlements = {};
  for(const p of PLACES_BUILTIN) settlements[p.id] = { pop:1 };
  return {
    era: 1,
    resources: { wood:0, stone:0, food:0, starlight:0 },
    settlements,
    buildings: [],
    totalTurns: 0,
  };
}

function defaultWorld(){
  return {
    currentPlace: 'grove',
    places: PLACES_BUILTIN.map(p=>({...p, beings:[...p.beings]})),
    beings: BEINGS_BUILTIN.map(b=>({...b})),
    maps: [],
    civ: defaultCiv(),
  };
}

function mergeState(saved){
  // Start from defaults and layer in saved values, adding new fields if missing
  const d = JSON.parse(JSON.stringify(DEFAULTS));
  if(!saved) return d;
  const merged = Object.assign({}, d, saved);
  // Always ensure new fields exist
  if(!merged.inventory)     merged.inventory     = [];
  if(!merged.pendingBonus)  merged.pendingBonus  = null;
  if(merged.mapState === undefined) merged.mapState = null;
  if(!merged.world || !merged.world.beings){
    merged.world = defaultWorld();
  }
  if(!merged.world.maps) merged.world.maps = [];
  if(!merged.world.civ)  merged.world.civ  = defaultCiv();
  if(!merged.world.civ.buildings) merged.world.civ.buildings = [];
  if(!merged.world.civ.resources) merged.world.civ.resources = { wood:0, stone:0, food:0, starlight:0 };
  if(!merged.world.civ.settlements) merged.world.civ.settlements = defaultCiv().settlements;
  if(merged.combat === undefined) merged.combat = null;
  return merged;
}

// ── Engine ────────────────────────────────────────────────────────────────────

function roll(sides){ return Math.floor(Math.random()*sides)+1; }

function skillCheck(stat, dc, helper, helperStat){
  const d = roll(20);
  const base = S.player[stat] || 0;
  let bonus = 0;
  if(helper && S[helper]){
    const hStat = S[helper][helperStat] || 0;
    const bond  = S[helper].bond || 0;
    bonus = Math.floor((hStat + bond/2) / 3);
  }
  // Apply pending bonus if it matches stat
  let pendingApplied = 0;
  if(S.pendingBonus && S.pendingBonus.stat === stat){
    pendingApplied = S.pendingBonus.bonus;
    S.pendingBonus = null;
  }
  const total = d + base + bonus + pendingApplied;
  return { d, base, bonus: bonus + pendingApplied, total, dc, pass: total >= dc, pendingApplied };
}

function addItemToInventory(itemId){
  if(itemId === '__merchant_random__'){
    const pool = ['glowstone','loki_notes','ancient_coin'];
    itemId = pool[Math.floor(Math.random()*pool.length)];
  }
  const template = ITEMS[itemId];
  if(!template) return null;
  // Stack consumables/tools if same item already in inventory (for tools, add uses)
  const existing = S.inventory.find(i => i.itemId === itemId);
  if(existing){
    existing.usesLeft = Math.min(existing.usesLeft + (template.uses || 1), (template.uses || 1) * 5);
    return template;
  }
  S.inventory.push({
    itemId,
    name:      template.name,
    emoji:     template.emoji,
    description: template.description,
    effect:    template.effect,
    usesLeft:  template.uses || null,
    usesMax:   template.uses || null,
  });
  return template;
}

function applyEffects(effects){
  if(!effects) return [];
  const pills = [];
  for(const [k,v] of Object.entries(effects)){
    if(k === 'item'){
      const added = addItemToInventory(v);
      if(added) pills.push({ text:`+${added.emoji} ${added.name}`, pos:true, item:true });
      continue;
    }
    const [obj,prop] = k.split('.');
    if(!S[obj]) continue;
    const old = S[obj][prop];
    if(prop === 'hp'){
      S[obj][prop] = Math.min(S[obj].maxHp, Math.max(0, (S[obj][prop]||0)+v));
    } else if(prop === 'bond'){
      S[obj][prop] = Math.min(10, Math.max(0, (S[obj][prop]||0)+v));
    } else if(['str','mag','wis','lck','heart','curiosity','craft','wit'].includes(prop)){
      S[obj][prop] = Math.min(5, Math.max(1, (S[obj][prop]||0)+v));
    }
    if(v !== 0){
      const label = prop==='hp'?'HP':prop==='bond'?`${S[obj].name} bond`:prop;
      const who   = prop==='bond'?'':S[obj].name+' ';
      pills.push({ text:`${v>0?'+':''}${v} ${who}${label}`, pos:v>0 });
    }
  }
  return pills;
}

function addMemory(scene, text){
  if(!text) return;
  S.memories.push({
    id: Date.now(),
    day: S.progress.day,
    chapter: S.progress.chapter,
    scene: scene.title,
    text,
  });
}

function pickScene(){
  if(S.progress.scenesThisChapter >= 5) return BOSS;
  const recent = S.recentScenes || [];
  let pool = POOL.filter(sc => !recent.includes(sc.id));
  if(!pool.length){ S.recentScenes=[]; pool=[...POOL]; }
  const total = pool.reduce((s,sc)=>s+sc.weight,0);
  let r = Math.random()*total;
  for(const sc of pool){ r-=sc.weight; if(r<=0) return sc; }
  return pool[0];
}

function save(){ localStorage.setItem('grove_v1', JSON.stringify(S)); }

function loadState(){
  try{ return JSON.parse(localStorage.getItem('grove_v1')); } catch{ return null; }
}

// ── World Helpers ─────────────────────────────────────────────────────────────

function getBeingById(id){
  return S.world.beings.find(b => b.id === id) || null;
}

function getCurrentPlace(){
  return S.world.places.find(p => p.id === S.world.currentPlace) || S.world.places[0];
}

function getBeingForScene(sceneType){
  if(sceneType !== 'encounter' && sceneType !== 'event') return null;
  const place = getCurrentPlace();
  if(!place || !place.beings || !place.beings.length) return null;
  const ids = place.beings.filter(id => S.world.beings.find(b=>b.id===id));
  if(!ids.length) return null;
  const id = ids[Math.floor(Math.random()*ids.length)];
  return getBeingById(id);
}

// ── Civilization Helpers ──────────────────────────────────────────────────────

function resIcon(key){ return {wood:'🪵',stone:'🪨',food:'🌾',starlight:'💫'}[key]||'?'; }

function getSettlementYield(placeId){
  const place = S.world.places.find(p=>p.id===placeId);
  if(!place) return {};
  const base = { ...(PLACE_YIELDS[place.type] || PLACE_YIELDS.custom) };
  if(S.world.civ.buildings.includes('tower')){
    for(const k in base) base[k]++;
  }
  return base;
}

function civAdvanceTurn(){
  const civ = S.world.civ;
  if(!civ) return null;
  civ.totalTurns++;
  const produced = { wood:0, stone:0, food:0, starlight:0 };
  for(const place of S.world.places){
    const settlement = civ.settlements[place.id];
    if(!settlement || settlement.pop < 1) continue;
    const yields = getSettlementYield(place.id);
    for(const [res, amt] of Object.entries(yields)){
      produced[res] = (produced[res]||0) + amt * settlement.pop;
      civ.resources[res] = (civ.resources[res]||0) + amt * settlement.pop;
    }
  }
  if(civ.buildings.includes('hearth')){
    S.player.hp = Math.min(S.player.maxHp, S.player.hp + 5);
    S.pucky.hp  = Math.min(S.pucky.maxHp,  S.pucky.hp  + 5);
    S.loki.hp   = Math.min(S.loki.maxHp,   S.loki.hp   + 5);
  }
  if(civ.buildings.includes('farm')) addItemToInventory('healers_leaf');
  civ.era = Math.min(3, Math.max(1, Math.ceil(S.progress.chapter / 2)));
  return produced;
}

function buildCivBuilding(buildingId){
  const civ = S.world.civ;
  const building = CIV_BUILDINGS.find(b=>b.id===buildingId);
  if(!building || civ.buildings.includes(buildingId)) return;
  for(const [res, amt] of Object.entries(building.cost)){
    if((civ.resources[res]||0) < amt) return;
  }
  for(const [res, amt] of Object.entries(building.cost)){
    civ.resources[res] -= amt;
  }
  civ.buildings.push(buildingId);
  switch(building.effect){
    case 'stat_loki_craft':  S.loki.craft  = Math.min(5, S.loki.craft+1);  break;
    case 'stat_player_wis':  S.player.wis  = Math.min(5, S.player.wis+1);  break;
    case 'stat_player_wis2': S.player.wis  = Math.min(5, S.player.wis+1);  break;
    case 'stat_pucky_heart': S.pucky.heart = Math.min(5, S.pucky.heart+1); break;
    case 'stat_player_lck':  S.player.lck  = Math.min(5, S.player.lck+1);  break;
  }
  save();
  renderRealm();
  renderParty();
}

// ── Render: Party ─────────────────────────────────────────────────────────────

function hpColor(hp, max){
  const pct = hp/max;
  return pct > 0.5 ? 'var(--pucky)' : pct > 0.25 ? 'var(--gold)' : 'var(--danger)';
}

function renderParty(){
  const chars = [
    { key:'player', cls:'u', hp:S.player.hp, max:S.player.maxHp, name:S.player.name, emoji:S.player.emoji },
    { key:'pucky',  cls:'p', hp:S.pucky.hp,  max:S.pucky.maxHp,  name:S.pucky.name,  emoji:S.pucky.emoji, bond:S.pucky.bond },
    { key:'loki',   cls:'l', hp:S.loki.hp,   max:S.loki.maxHp,   name:S.loki.name,   emoji:S.loki.emoji,  bond:S.loki.bond },
  ];
  document.getElementById('party').innerHTML = chars.map(c=>`
    <div class="char-card">
      <div class="char-emoji">${c.emoji}</div>
      <div class="char-name-sm ${c.cls}">${c.name}</div>
      <div class="hpbar"><div class="hpbar-fill" style="width:${c.hp/c.max*100}%;background:${hpColor(c.hp,c.max)}"></div></div>
      ${c.bond!==undefined?`<div style="font-size:.6em;color:var(--dimmer);margin-top:2px">bond ${c.bond}/10</div>`:''}
    </div>`).join('');

  // Update inventory button badge
  const badge = document.getElementById('inv-badge');
  if(badge) badge.textContent = S.inventory.length || '';

  // Update location hint
  const loc = document.getElementById('location-hint');
  if(loc){
    const place = getCurrentPlace();
    if(place){
      const placeMap = S.world.maps.find(m=>m.placeId===place.id);
      const exploreBtn = placeMap && !S.mapState
        ? `<button class="map-explore-btn" onclick="enterMap('${placeMap.id}')">🗺 explore →</button>`
        : '';
      loc.innerHTML = `<span>📍 ${esc(place.name)}</span>${exploreBtn}`;
    } else {
      loc.textContent = '';
    }
  }

  // Update pending bonus indicator
  const pb = document.getElementById('pending-bonus');
  if(pb){
    if(S.pendingBonus){
      pb.textContent = `+${S.pendingBonus.bonus} ${S.pendingBonus.stat} ready`;
      pb.style.display = '';
    } else {
      pb.style.display = 'none';
    }
  }
}

// ── Render: Scene ─────────────────────────────────────────────────────────────

function getScene(id){
  if(id==='__intro__') return INTRO;
  if(id==='__boss__')  return BOSS;
  return POOL.find(s=>s.id===id) || INTRO;
}

function renderScene(scene){
  const sa = document.getElementById('scene-area');
  const ca = document.getElementById('choices-area');
  const text = typeof scene.text === 'function' ? scene.text(S) : scene.text;
  sa.innerHTML = `
    <div class="scene-title" style="animation:rise .3s ease">${scene.title}</div>
    <div class="scene-text"  style="animation:rise .35s ease">${text}</div>`;
  ca.innerHTML = scene.choices.map((c,i)=>{
    const choiceText = typeof c.text === 'function' ? c.text(S) : c.text;
    const check = c.stat ? `<div class="check">${c.stat.toUpperCase()} check · DC ${c.dc}${c.helper?` · ${S[c.helper].name} helps`:''}</div>` : '';
    return `<button class="choice-btn" onclick="choose(${i})">${choiceText}${check}</button>`;
  }).join('');

  // Auto-play voice if scene has an associated being with a recording
  if(scene.beingType){
    const being = S.world.beings.find(b => b.type === scene.beingType);
    if(being && _voiceHas[being.id]){
      setTimeout(() => playVoice(being.id), 500);
    }
  }
}

function choose(i){
  const scene  = getScene(S.currentSceneId);
  const choice = scene.choices[i];
  const ca     = document.getElementById('choices-area');
  const sa     = document.getElementById('scene-area');

  if(!choice.stat){
    const out = choice.win(S);
    const pills = applyEffects(out.effects);
    if(out.memory) addMemory(scene, out.memory);
    sa.innerHTML += `<div class="outcome-text" style="animation:rise .3s ease">${out.text}</div>
      <div class="effect-pills">${pills.map(p=>`<span class="pill ${p.pos?(p.item?'item':'pos'):'neg'}">${p.text}</span>`).join('')}</div>`;
    ca.innerHTML = `<button class="continue-btn" onclick="advance()">continue →</button>`;
    renderParty();
    save();
    return;
  }

  // Dice roll
  ca.innerHTML = '';
  const faces  = ['⚀','⚁','⚂','⚃','⚄','⚅'];
  sa.innerHTML += `<div class="die-wrap" id="die">⚀</div>`;
  const dieEl  = document.getElementById('die');
  let ticks = 0;
  const iv = setInterval(()=>{
    dieEl.textContent = faces[Math.floor(Math.random()*6)];
    ticks++;
    if(ticks >= 12){
      clearInterval(iv);
      const result = skillCheck(choice.stat, choice.dc, choice.helper, choice.helperStat);
      dieEl.innerHTML = `${faces[result.d-1]}<div class="die-result ${result.pass?'win':'lose'}">${result.pass?'success':'failure'} · rolled ${result.d}+${result.base+result.bonus} vs DC ${result.dc}</div>`;
      const out  = result.pass ? choice.win(S) : (choice.lose ? choice.lose(S) : choice.win(S));
      const pills = applyEffects(out.effects);
      if(out.memory) addMemory(scene, out.memory);
      renderParty();
      sa.innerHTML += `<div class="outcome-text" style="animation:rise .3s ease">${out.text}</div>
        <div class="effect-pills">${pills.map(p=>`<span class="pill ${p.pos?(p.item?'item':'pos'):'neg'}">${p.text}</span>`).join('')}</div>`;
      ca.innerHTML = `<button class="continue-btn" onclick="advance()">continue →</button>`;
      save();
      const scr = document.getElementById('scene-area');
      setTimeout(()=>scr.scrollTop=scr.scrollHeight, 50);
    }
  }, 60);
}

function advance(){
  const wasBoss = S.currentSceneId === '__boss__';
  const oldChapter = S.progress.chapter;
  if(wasBoss){
    S.progress.chapter++;
    S.progress.scenesThisChapter=0;
    S.progress.day++;
    const produced = civAdvanceTurn();
    save();
    renderParty();
    showChapterComplete(oldChapter, produced);
  } else {
    S.progress.scenesThisChapter++;
    S.progress.totalScenes++;
    if(!S.recentScenes) S.recentScenes=[];
    S.recentScenes.push(S.currentSceneId);
    if(S.recentScenes.length > 5) S.recentScenes.shift();
    if(maybeEncounterMonster()) return;
    const next = pickScene();
    S.currentSceneId = next.id;
    save();
    renderParty();
    renderScene(next);
    document.getElementById('scene-area').scrollTop = 0;
  }
}

function showChapterComplete(ch, produced){
  const sa = document.getElementById('scene-area');
  const ca = document.getElementById('choices-area');
  const chMems = S.memories.filter(m => m.chapter === ch);
  const preview = chMems.slice(-3).map(m =>
    `<div class="ch-mem-line">· ${m.text}</div>`).join('');
  let harvestHTML = '';
  if(produced){
    const parts = Object.entries(produced).filter(([,v])=>v>0).map(([k,v])=>`${v}${resIcon(k)}`);
    if(parts.length) harvestHTML = `<div class="realm-harvest">realm harvest: ${parts.join(' · ')}</div>`;
  }
  sa.innerHTML = `
    <div class="scene-title" style="animation:rise .3s ease">chapter ${ch} complete</div>
    <div class="ch-card" style="animation:rise .35s ease">
      <div class="ch-day">day ${S.progress.day - 1} · ${chMems.length} ${chMems.length===1?'memory':'memories'} kept</div>
      ${preview ? `<div class="ch-mems">${preview}</div>` : ''}
      ${harvestHTML}
    </div>`;
  ca.innerHTML = `
    <button class="choice-btn" onclick="saveMemoriesThenContinue()">📖 save memories → continue</button>
    <button class="continue-btn" onclick="continueFromChapter()">continue →</button>`;
  document.getElementById('scene-area').scrollTop = 0;
}

function saveMemoriesThenContinue(){
  downloadMemories();
  setTimeout(continueFromChapter, 400);
}

function continueFromChapter(){
  const next = pickScene();
  S.currentSceneId = next.id;
  save();
  renderParty();
  renderScene(next);
  document.getElementById('scene-area').scrollTop = 0;
}

// ── Inventory ─────────────────────────────────────────────────────────────────

function openInventory(){
  document.getElementById('inv-overlay').classList.add('on');
  renderInventoryPanel();
}

function closeInventory(){
  document.getElementById('inv-overlay').classList.remove('on');
}

function renderInventoryPanel(){
  const list = document.getElementById('inv-list');
  if(!S.inventory.length){
    list.innerHTML = '<div class="inv-empty">nothing carried</div>';
    return;
  }
  list.innerHTML = S.inventory.map((item, idx) => {
    const usesLabel = item.usesLeft !== null
      ? `<div class="item-uses">${item.usesLeft} use${item.usesLeft===1?'':'s'} left</div>` : '';
    const canUse = item.usesLeft === null || item.usesLeft > 0;
    const useBtn = canUse
      ? `<button class="item-use-btn" onclick="useItem(${idx})">use</button>` : '';
    return `<div class="item-row">
      <div class="item-emoji">${item.emoji}</div>
      <div class="item-info">
        <div class="item-name">${item.name}</div>
        <div class="item-desc">${item.description}</div>
        ${usesLabel}
      </div>
      ${useBtn}
    </div>`;
  }).join('');
}

function useItem(idx){
  const item = S.inventory[idx];
  if(!item) return;
  const eff = item.effect;
  let msg = '';

  if(eff.hp){
    // restore HP to player
    S.player.hp = Math.min(S.player.maxHp, S.player.hp + eff.hp);
    msg = `${item.emoji} Restored ${eff.hp} HP.`;
  } else if(eff.allHp){
    S.player.hp  = Math.min(S.player.maxHp,  S.player.hp  + eff.allHp);
    S.pucky.hp   = Math.min(S.pucky.maxHp,   S.pucky.hp   + eff.allHp);
    S.loki.hp    = Math.min(S.loki.maxHp,    S.loki.hp    + eff.allHp);
    msg = `${item.emoji} Restored ${eff.allHp} HP to everyone.`;
  } else if(eff.stat){
    S.pendingBonus = { stat: eff.stat, bonus: eff.bonus };
    msg = `${item.emoji} +${eff.bonus} ${eff.stat} on next ${eff.stat} check.`;
  } else if(eff.reroll){
    S.pendingBonus = { stat: '__reroll__', bonus: 0, reroll: true };
    msg = `${item.emoji} Will re-roll on next failure.`;
  }

  // Decrement uses or remove
  if(item.usesLeft !== null){
    item.usesLeft--;
    if(item.usesLeft <= 0){
      S.inventory.splice(idx, 1);
    }
  }

  save();
  renderParty();
  renderInventoryPanel();
  if(msg){
    // Flash a small message
    const head = document.querySelector('.inv-panel-head h2');
    if(head){ const orig = head.textContent; head.textContent = msg; setTimeout(()=>head.textContent=orig, 2000); }
  }
}

// ── Companions Tab ────────────────────────────────────────────────────────────

const EMOJIS = ['🌿','🌱','🍀','🌸','🌙','⭐','🔮','🦊','🐺','🦉','🐸','🐝','🦋',
                '🔧','⚒️','🛡️','⚔️','🌊','🔥','❄️','🌈','🍄','🐉','🦌','🐇'];

function statEditor(charKey, statKey, label, color){
  const val = S[charKey][statKey];
  return `<div class="stat-row">
    <label style="color:${color||'var(--dim)'}">${label}</label>
    <div class="stat-controls">
      <button class="stat-btn" onclick="adjStat('${charKey}','${statKey}',-1)">−</button>
      <span class="stat-val" id="sv-${charKey}-${statKey}">${val}</span>
      <button class="stat-btn" onclick="adjStat('${charKey}','${statKey}',1)">+</button>
    </div>
  </div>`;
}

function adjStat(charKey, statKey, delta){
  S[charKey][statKey] = Math.min(5, Math.max(1, S[charKey][statKey]+delta));
  document.getElementById(`sv-${charKey}-${statKey}`).textContent = S[charKey][statKey];
  save();
}

function setName(charKey, val){ S[charKey].name=val; save(); renderParty(); }
function setEmoji(charKey, val){ S[charKey].emoji=val; save(); renderParty(); }
function setPhrase(charKey, phraseKey, val){ S[charKey].phrases[phraseKey]=val; save(); }

function showEmojiPicker(charKey){
  document.getElementById(`ep-${charKey}`).classList.toggle('on');
}

function pickEmoji(charKey, emoji){
  S[charKey].emoji = emoji;
  document.getElementById(`einput-${charKey}`).value = emoji;
  document.getElementById(`ep-${charKey}`).classList.remove('on');
  save(); renderParty();
}

function renderCompanions(){
  const comp = document.getElementById('comp');
  const chars = [
    { key:'player', cls:'u', label:'You', stats:[['str','STR'],['mag','MAG'],['wis','WIS'],['lck','LCK']], phraseKeys:[] },
    { key:'pucky',  cls:'p', label:S.pucky.name, stats:[['heart','HEART'],['curiosity','CURIOSITY']], phraseKeys:['greeting','curious','success','failure','scared','memory'] },
    { key:'loki',   cls:'l', label:S.loki.name,  stats:[['craft','CRAFT'],['wit','WIT']], phraseKeys:['greeting','plan','success','failure','craft','memory'] },
  ];

  comp.innerHTML = chars.map(c=>`
  <div class="comp-card">
    <div class="comp-header">
      <div class="comp-emoji-big" onclick="showEmojiPicker('${c.key}')">${S[c.key].emoji}</div>
      <div class="comp-title">
        <h3 class="${c.cls}">${c.label}</h3>
        ${c.key!=='player'?`<div class="bond-bar"><div class="bond-fill" style="width:${S[c.key].bond*10}%"></div></div>`:''}
      </div>
    </div>
    <div class="emoji-picker" id="ep-${c.key}">
      ${EMOJIS.map(e=>`<span class="epick" onclick="pickEmoji('${c.key}','${e}')">${e}</span>`).join('')}
    </div>
    <div class="field">
      <label>Name</label>
      <input id="einput-${c.key}" value="${S[c.key].name}" oninput="setName('${c.key}',this.value)">
    </div>
    <div class="field">
      <label>Emoji</label>
      <input value="${S[c.key].emoji}" oninput="setEmoji('${c.key}',this.value)" maxlength="2" style="width:60px">
    </div>
    <div class="stats-grid">
      ${c.stats.map(([sk,sl])=>statEditor(c.key,sk,sl)).join('')}
    </div>
    ${c.phraseKeys.length?`<div class="phrases-section">
      <details>
        <summary>phrases</summary>
        <div class="phrases-grid">
          ${c.phraseKeys.map(pk=>`<div class="phrase-row">
            <div class="phrase-label">${pk}</div>
            <input value="${(S[c.key].phrases[pk]||'').replace(/"/g,'&quot;')}" oninput="setPhrase('${c.key}','${pk}',this.value)">
          </div>`).join('')}
        </div>
      </details>
    </div>`:''}
  </div>`).join('');
}

// ── VoiceDB ───────────────────────────────────────────────────────────────────

const VDB = (() => {
  let _db = null;
  function open() {
    return new Promise((res, rej) => {
      if (_db) { res(_db); return; }
      const req = indexedDB.open('grove_voices', 1);
      req.onupgradeneeded = e => e.target.result.createObjectStore('clips');
      req.onsuccess = e => { _db = e.target.result; res(_db); };
      req.onerror = () => rej(req.error);
    });
  }
  async function op(mode, fn) {
    const db = await open();
    return new Promise((res, rej) => {
      const t = db.transaction('clips', mode);
      const r = fn(t.objectStore('clips'));
      r.onsuccess = () => res(r.result);
      r.onerror  = () => rej(r.error);
    });
  }
  return {
    save:   (id, blob) => op('readwrite', s => s.put(blob, id)),
    load:   (id)       => op('readonly',  s => s.get(id)),
    remove: (id)       => op('readwrite', s => s.delete(id)),
    has:    async (id) => (await op('readonly', s => s.get(id))) != null,
  };
})();

// ── Voice Recording ───────────────────────────────────────────────────────────

let _recorder = null;
let _recChunks = [];
let _recBeingId = null;
let _voiceHas = {}; // cache: beingId -> bool

async function refreshVoiceStates() {
  for (const b of S.world.beings) {
    _voiceHas[b.id] = await VDB.has(b.id);
  }
}

async function startRecording(beingId) {
  if (_recorder) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    _recChunks = [];
    _recBeingId = beingId;
    _recorder = new MediaRecorder(stream);
    _recorder.ondataavailable = e => { if (e.data.size > 0) _recChunks.push(e.data); };
    _recorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(_recChunks, { type: _recorder.mimeType || 'audio/webm' });
      await VDB.save(_recBeingId, blob);
      _voiceHas[_recBeingId] = true;
      _recorder = null;
      _recBeingId = null;
      renderWorldContent();
    };
    _recorder.start();
    renderWorldContent(); // show ⏹ stop button
  } catch(e) {
    _recorder = null;
    _recBeingId = null;
    alert('Microphone access needed.\n\niPhone: Settings → Safari → Microphone → Allow.');
  }
}

function stopRecording() {
  if (_recorder && _recorder.state === 'recording') _recorder.stop();
}

async function playVoice(beingId) {
  const blob = await VDB.load(beingId);
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  const a = new Audio(url);
  a.onended = () => URL.revokeObjectURL(url);
  a.play().catch(() => {});
}

async function deleteVoice(beingId) {
  await VDB.remove(beingId);
  _voiceHas[beingId] = false;
  renderWorldContent();
}

// ── Battle Yell ───────────────────────────────────────────────────────────────

const YELL_KEY = '__player_yell__';
let _yellRecorder = null;
let _yellChunks   = [];
let _yellHas      = false;

async function initYellCheck(){
  _yellHas = await VDB.has(YELL_KEY);
  renderYellBtn();
}

function renderYellBtn(){
  const btn = document.getElementById('yell-btn');
  if(!btn) return;
  btn.classList.toggle('yell-recording', !!_yellRecorder);
  btn.classList.toggle('yell-ready', _yellHas && !_yellRecorder);
  btn.title = _yellRecorder ? 'Stop recording' : (_yellHas ? 'Battle cry recorded — tap to re-record' : 'Record your battle cry');
}

async function toggleYellRecord(){
  if(_yellRecorder){
    _yellRecorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio:true });
    _yellChunks = [];
    _yellRecorder = new MediaRecorder(stream);
    _yellRecorder.ondataavailable = e => _yellChunks.push(e.data);
    _yellRecorder.onstop = async () => {
      const blob = new Blob(_yellChunks, { type:'audio/webm' });
      await VDB.save(YELL_KEY, blob);
      _yellHas = true;
      _yellRecorder = null;
      stream.getTracks().forEach(t => t.stop());
      renderYellBtn();
      // Refresh pre-encounter if open
      if(S.combat && S.combat.preEncounter) renderCombatPreEncounter();
    };
    _yellRecorder.start();
    renderYellBtn();
  } catch(err){
    alert('Microphone access needed to record your battle cry.');
  }
}

async function playYell(hitType){
  const blob = await VDB.load(YELL_KEY);
  if(!blob) return;
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const buf = await ctx.decodeAudioData(await blob.arrayBuffer());

  function once(rate, delay){
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.playbackRate.value = rate;
    src.connect(ctx.destination);
    src.start(ctx.currentTime + delay);
  }

  if(hitType === 'heavy'){
    once(0.65, 0);                         // one slow, low, powerful yell
  } else if(hitType === 'light'){
    once(1.5, 0); once(1.6, 0.18); once(1.45, 0.34); // three fast, high yells
  } else {
    once(1.0, 0);                          // normal single yell
  }
}

async function deleteYell(){
  await VDB.remove(YELL_KEY);
  _yellHas = false;
  renderYellBtn();
  if(S.combat && S.combat.preEncounter) renderCombatPreEncounter();
}

// ── Combat ────────────────────────────────────────────────────────────────────

function pickMonster(){
  return { ...MONSTERS[Math.floor(Math.random() * MONSTERS.length)] };
}

// Called from advance() — 28% chance of encounter after first scene
function maybeEncounterMonster(){
  if(S.progress.scenesThisChapter < 1) return false;
  if(Math.random() > 0.28) return false;
  const monster = pickMonster();
  S.combat = { monster, monsterHp: monster.hp, round: 1, log: [], preEncounter: true };
  S.phase = 'combat';
  save();
  renderCombatPreEncounter();
  renderParty();
  return true;
}

function renderCombatPreEncounter(){
  const m = S.combat.monster;
  const sa = document.getElementById('scene-area');
  const ca = document.getElementById('choices-area');
  const recording = !!_yellRecorder;

  sa.innerHTML = `
    <div class="scene-title" style="animation:rise .3s ease">⚔️ encounter!</div>
    <div class="combat-pre" style="animation:rise .35s ease">
      <div class="monster-reveal">
        <div class="monster-emoji-big">${m.emoji}</div>
        <div class="monster-name-big">${esc(m.name)}</div>
        <div class="monster-stats-row">
          <span class="monster-stat-chip">❤️ ${m.hp} HP</span>
          <span class="monster-stat-chip">⚔️ STR ${m.str}</span>
          <span class="monster-stat-chip">🛡 DEF ${m.def}</span>
        </div>
        <div class="monster-desc-pre">"${esc(m.desc)}"</div>
      </div>
      <div class="yell-setup">
        <div class="yell-setup-label">🎙 battle cry</div>
        <div class="yell-setup-desc">Your yell plays on every hit — low &amp; slow for heavy blows, fast &amp; triple for quick strikes.</div>
        <div class="yell-btns">
          <button class="yell-setup-btn${recording?' yell-setup-recording':''}" onclick="toggleYellRecord()">
            ${recording ? '⏹ stop' : (_yellHas ? '🎙 re-record' : '🎙 record battle cry')}
          </button>
          ${_yellHas && !recording ? `<button class="yell-setup-btn" onclick="playYell('normal')">▶ test</button>` : ''}
          ${_yellHas && !recording ? `<button class="yell-setup-btn danger" onclick="deleteYell()">✕</button>` : ''}
        </div>
        ${_yellHas ? `<div class="yell-ready-notice">✓ battle cry ready</div>` : `<div class="yell-no-notice">No battle cry — you can still fight!</div>`}
      </div>
    </div>`;

  ca.innerHTML = `
    <button class="choice-btn" onclick="startFight()">⚔️ fight!</button>
    <button class="choice-btn" onclick="fleeEncounter()">🏃 run for it</button>`;
}

function startFight(){
  S.combat.preEncounter = false;
  save();
  renderCombatScene();
}

function renderCombatScene(){
  const c = S.combat;
  const sa = document.getElementById('scene-area');
  const ca = document.getElementById('choices-area');
  const mPct = Math.max(0, c.monsterHp / c.monster.hp * 100);
  const pPct = Math.max(0, S.player.hp  / S.player.maxHp  * 100);

  const logLines = c.log.slice(-5).map((line,i)=>
    `<div class="combat-log-line" style="opacity:${.45 + i*.11}">${line}</div>`).join('');

  sa.innerHTML = `
    <div class="scene-title">⚔️ round ${c.round}</div>
    <div class="combat-arena">
      <div class="combatant enemy">
        <div class="combatant-emoji">${c.monster.emoji}</div>
        <div class="combatant-name">${esc(c.monster.name)}</div>
        <div class="combat-hpbar"><div class="combat-hpfill enemy" style="width:${mPct}%"></div></div>
        <div class="combat-hp-num">${c.monsterHp} / ${c.monster.hp}</div>
      </div>
      <div class="combat-vs">vs</div>
      <div class="combatant player">
        <div class="combatant-emoji">${S.player.emoji}</div>
        <div class="combatant-name">${esc(S.player.name)}</div>
        <div class="combat-hpbar"><div class="combat-hpfill player" style="width:${pPct}%"></div></div>
        <div class="combat-hp-num">${S.player.hp} / ${S.player.maxHp}</div>
      </div>
    </div>
    <div class="combat-log">${logLines}</div>`;

  const hasItems = S.inventory.length > 0;
  ca.innerHTML = `
    <button class="choice-btn" onclick="combatAttack()">⚔️ attack <span class="check">STR · DC ${c.monster.def}</span></button>
    ${hasItems ? `<button class="choice-btn" onclick="openInventory()">🎒 use item</button>` : ''}
    <button class="choice-btn" onclick="combatFlee()">🏃 flee <span class="check">LCK · DC 12</span></button>`;
}

function combatAttack(){
  const c = S.combat;
  const d = roll(20);
  const total = d + S.player.str;
  const dc = c.monster.def;
  const margin = total - dc;

  if(d === 20 || total >= dc){
    let dmg = roll(6) + S.player.str;
    let hitType, line;

    if(d === 20 || margin >= 5){
      hitType = 'heavy';
      dmg = Math.round(dmg * 1.8);
      line = d === 20
        ? `💥 Critical strike! ${dmg} damage! (natural 20)`
        : `💪 Heavy blow — ${dmg} damage! (${d}+${S.player.str}=${total} vs DC ${dc})`;
    } else if(margin <= 1){
      hitType = 'light';
      const strikes = roll(2) + 1;
      dmg = Math.max(1, Math.round(dmg * 0.55));
      line = `⚡ ${strikes} quick strikes — ${dmg} damage. (${d}+${S.player.str}=${total} vs DC ${dc})`;
    } else {
      hitType = 'normal';
      line = `Hit — ${dmg} damage. (${d}+${S.player.str}=${total} vs DC ${dc})`;
    }

    playYell(hitType);
    c.monsterHp = Math.max(0, c.monsterHp - dmg);
    c.log.push(line);

    if(c.monsterHp <= 0){ endCombat(true); return; }
  } else {
    c.log.push(`Missed. (${d}+${S.player.str}=${total} vs DC ${dc})`);
  }

  monsterHits();
}

function monsterHits(){
  const c  = S.combat;
  const d  = roll(20);
  const dc = 10 + Math.floor(S.player.wis / 2);
  const total = d + c.monster.str;

  if(total >= dc){
    const dmg = roll(4) + c.monster.str;
    S.player.hp = Math.max(0, S.player.hp - dmg);
    c.log.push(`${c.monster.emoji} ${c.monster.name} hits for ${dmg}! (${S.player.hp} HP left)`);
    if(S.player.hp <= 0){ endCombat(false); return; }
  } else {
    c.log.push(`${c.monster.emoji} ${c.monster.name} misses.`);
  }

  c.round++;
  save();
  renderParty();
  renderCombatScene();
}

function combatFlee(){
  const d = roll(20);
  const total = d + S.player.lck;
  if(total >= 12){
    S.combat.log.push(`Escaped! (${d}+${S.player.lck}=${total} vs DC 12)`);
    S.combat = null; S.phase = 'scene'; save();
    renderScene(getScene(S.currentSceneId));
  } else {
    S.combat.log.push(`Failed to flee! (${d}+${S.player.lck}=${total} vs DC 12)`);
    monsterHits();
  }
}

function fleeEncounter(){
  S.combat = null; S.phase = 'scene'; save();
  renderScene(getScene(S.currentSceneId));
}

function endCombat(victory){
  const monster = S.combat.monster;
  S.combat = null; S.phase = 'scene';
  const sa = document.getElementById('scene-area');
  const ca = document.getElementById('choices-area');

  if(victory){
    sa.innerHTML = `
      <div class="scene-title" style="animation:rise .3s ease">⚔️ victory!</div>
      <div class="ch-card" style="animation:rise .35s ease">
        <div class="ch-day">${monster.emoji} ${esc(monster.name)} defeated</div>
        <div style="font-size:.88em;color:var(--dim);margin-top:10px;line-height:1.7">
          The grove grows a little quieter. Your party catches their breath.</div>
      </div>`;
  } else {
    S.player.hp = Math.max(1, Math.floor(S.player.maxHp * 0.15));
    sa.innerHTML = `
      <div class="scene-title" style="animation:rise .3s ease">💀 overwhelmed</div>
      <div class="ch-card" style="animation:rise .35s ease">
        <div class="ch-day">You had to retreat.</div>
        <div style="font-size:.88em;color:var(--dim);margin-top:10px;line-height:1.7">
          Battered, your party pulls back. HP restored to ${S.player.hp}. Press on.</div>
      </div>`;
  }
  ca.innerHTML = `<button class="continue-btn" onclick="continueAfterCombat()">continue →</button>`;
  save(); renderParty();
}

function continueAfterCombat(){
  const next = pickScene();
  S.currentSceneId = next.id;
  save(); renderParty(); renderScene(next);
  document.getElementById('scene-area').scrollTop = 0;
}

// ── World Tab ─────────────────────────────────────────────────────────────────

let worldSubtab = 'places';
// Track which cards have edit forms open: Map of id -> true
const worldEditOpen = {};

function setWorldSubtab(tab){
  worldSubtab = tab;
  document.querySelectorAll('.world-subtab').forEach(el=>{
    el.classList.toggle('on', el.dataset.tab === tab);
  });
  renderWorldContent();
}

async function renderWorld(){
  await refreshVoiceStates();
  renderWorldContent();
}

function beingTypeBadge(type){
  const cls = ['tavern','merchant','spirit','creature','builder'].includes(type) ? type : 'custom';
  return `<span class="being-type-badge badge-${cls}">${type}</span>`;
}

function renderWorldContent(){
  const wc = document.getElementById('world-content');
  if(worldSubtab === 'places'){
    wc.innerHTML = renderPlaces();
  } else if(worldSubtab === 'maps'){
    wc.innerHTML = renderMaps();
  } else if(worldSubtab === 'realm'){
    wc.innerHTML = buildRealmHTML();
  } else {
    wc.innerHTML = renderBeings();
  }
}

function renderPlaces(){
  const places = S.world.places;
  const cards = places.map((place, idx) => {
    const isCurrent = place.id === S.world.currentPlace;
    const beingNames = (place.beings || []).map(bid => {
      const b = getBeingById(bid);
      return b ? `${b.emoji} ${b.name}` : null;
    }).filter(Boolean).join(', ');

    const travelBtn = isCurrent
      ? `<button class="place-travel-btn here" disabled>here now</button>`
      : `<button class="place-travel-btn" onclick="travelTo('${place.id}')">travel here</button>`;

    const editBtn = `<button class="world-action-btn" onclick="togglePlaceEdit('${place.id}')">edit</button>`;
    const delBtn  = place.custom ? `<button class="world-action-btn del" onclick="deletePlace('${place.id}')">delete</button>` : '';

    const editForm = worldEditOpen[place.id] ? `
      <div class="place-edit-form">
        <div class="world-field">
          <label>Name</label>
          <input value="${esc(place.name)}" oninput="updatePlace('${place.id}','name',this.value)">
        </div>
        <div class="world-field">
          <label>Emoji</label>
          <input value="${esc(place.emoji)}" oninput="updatePlace('${place.id}','emoji',this.value)" style="width:60px">
        </div>
        <div class="world-field">
          <label>Description</label>
          <textarea rows="2" oninput="updatePlace('${place.id}','description',this.value)">${esc(place.description)}</textarea>
        </div>
      </div>` : '';

    return `<div class="place-card${isCurrent?' current':''}">
      <div class="place-card-head">
        <div class="place-emoji">${place.emoji}</div>
        <div class="place-meta">
          <div class="place-name">${isCurrent?'<div class="place-current-dot"></div>':''}${esc(place.name)}</div>
          <div class="place-type">${place.type}</div>
        </div>
      </div>
      <div class="place-desc">${esc(place.description)}</div>
      ${beingNames ? `<div class="place-beings-list">beings here: ${beingNames}</div>` : ''}
      <div class="place-actions">
        ${travelBtn}${editBtn}${delBtn}
      </div>
      ${editForm}
    </div>`;
  }).join('');

  return `<div class="place-grid">${cards}</div>
    <button class="world-add-btn" onclick="addPlace()">+ create place</button>`;
}

function renderBeings(){
  const beings = S.world.beings;
  const cards = beings.map((being) => {
    const editBtn = `<button class="world-action-btn" onclick="toggleBeingEdit('${being.id}')">edit</button>`;
    const delBtn  = being.custom ? `<button class="world-action-btn del" onclick="deleteBeing('${being.id}')">delete</button>` : '';

    const editForm = worldEditOpen['being_'+being.id] ? `
      <div class="being-edit-form">
        <div class="world-field">
          <label>Name</label>
          <input value="${esc(being.name)}" oninput="updateBeing('${being.id}','name',this.value)">
        </div>
        <div class="world-field">
          <label>Emoji</label>
          <input value="${esc(being.emoji)}" oninput="updateBeing('${being.id}','emoji',this.value)" style="width:60px">
        </div>
        <div class="world-field">
          <label>Description</label>
          <textarea rows="2" oninput="updateBeing('${being.id}','description',this.value)">${esc(being.description)}</textarea>
        </div>
        <div class="world-field">
          <label>Phrase</label>
          <input value="${esc(being.phrase)}" oninput="updateBeing('${being.id}','phrase',this.value)">
        </div>
      </div>` : '';

    const hasVoice   = _voiceHas[being.id] || false;
    const isRecording = _recBeingId === being.id;
    const voiceControls = `<div class="voice-controls">
      ${isRecording
        ? `<button class="voice-btn rec" onclick="stopRecording()">⏹ stop</button><span class="rec-dot">●</span>`
        : `<button class="voice-btn"     onclick="startRecording('${being.id}')">🎤 record voice</button>`}
      ${hasVoice && !isRecording ? `<button class="voice-btn play" onclick="playVoice('${being.id}')">▶ play</button>` : ''}
      ${hasVoice && !isRecording ? `<button class="voice-btn"      onclick="deleteVoice('${being.id}')">✕ voice</button>` : ''}
    </div>`;

    return `<div class="being-card">
      <div class="being-head">
        <div class="being-emoji">${being.emoji}</div>
        <div class="being-meta">
          <div class="being-name">${esc(being.name)}${hasVoice ? ' <span class="voice-has">🎤</span>' : ''}</div>
          ${beingTypeBadge(being.type)}
        </div>
      </div>
      <div class="being-desc">${esc(being.description)}</div>
      <div class="being-phrase">"${esc(being.phrase)}"</div>
      ${voiceControls}
      <div class="being-actions">
        ${editBtn}${delBtn}
      </div>
      ${editForm}
    </div>`;
  }).join('');

  return `<div class="being-list">${cards}</div>
    <button class="world-add-btn" onclick="addBeing()">+ create being</button>`;
}

function esc(str){ return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function travelTo(placeId){
  S.world.currentPlace = placeId;
  save();
  renderParty();
  renderWorldContent();
}

function togglePlaceEdit(placeId){
  worldEditOpen[placeId] = !worldEditOpen[placeId];
  renderWorldContent();
}

function toggleBeingEdit(beingId){
  const key = 'being_'+beingId;
  worldEditOpen[key] = !worldEditOpen[key];
  renderWorldContent();
}

function updatePlace(placeId, field, value){
  const place = S.world.places.find(p=>p.id===placeId);
  if(place){ place[field] = value; save(); }
  // Re-render party to update location hint if name changed
  if(field === 'name') renderParty();
}

function updateBeing(beingId, field, value){
  const being = S.world.beings.find(b=>b.id===beingId);
  if(being){ being[field] = value; save(); }
}

function addPlace(){
  const id = 'custom_place_' + Date.now();
  S.world.places.push({ id, name:'New Place', emoji:'🗺️', type:'custom', description:'A place to describe.', beings:[], custom:true });
  if(S.world.civ && !S.world.civ.settlements[id]) S.world.civ.settlements[id] = { pop:1 };
  worldEditOpen[id] = true;
  save();
  renderWorldContent();
}

function deletePlace(placeId){
  S.world.places = S.world.places.filter(p=>p.id!==placeId);
  if(S.world.currentPlace === placeId) S.world.currentPlace = 'grove';
  save();
  renderWorldContent();
}

function addBeing(){
  const id = 'custom_being_' + Date.now();
  S.world.beings.push({ id, name:'New Being', emoji:'✨', type:'custom', description:'A being to describe.', phrase:'...', custom:true });
  worldEditOpen['being_'+id] = true;
  save();
  renderWorldContent();
}

function deleteBeing(beingId){
  S.world.beings = S.world.beings.filter(b=>b.id!==beingId);
  save();
  renderWorldContent();
}

// ── Maps ──────────────────────────────────────────────────────────────────────

let mapEditorPlaceId = null;
const mapRoomEditOpen = {}; // roomId -> bool
const mapExitFormOpen = {}; // roomId -> bool

function getMapForPlace(placeId){
  return S.world.maps.find(m=>m.placeId===placeId) || null;
}

function renderMaps(){
  const places = S.world.places;
  const sel = mapEditorPlaceId || (places[0] ? places[0].id : null);
  mapEditorPlaceId = sel;

  const guide = `<div class="map-guide">
    <div class="map-guide-title">🗺 how to build a map</div>
    <ol class="map-guide-steps">
      <li>Pick a <strong>place</strong> from the dropdown above</li>
      <li>Click <strong>+ create map</strong> — you get one starting room automatically</li>
      <li>Click <strong>+ add room</strong> for each additional room you want</li>
      <li>Click <strong>edit</strong> on a room to set its name, description, and beings</li>
      <li>Click <strong>add exit</strong> to connect rooms — type a direction like <em>north</em>, <em>south</em>, <em>up</em>, <em>down</em>, or anything descriptive like <em>through the archway</em></li>
      <li>If you have multiple rooms, click <strong>set start</strong> on the room players should enter first</li>
      <li>Go to the <strong>Adventure tab</strong> and look for the <strong>🗺 explore</strong> button to walk through your map in the game</li>
    </ol>
    <div class="map-guide-tip">💡 Use <em>north / south / east / west</em> as exit labels and the minimap will draw itself automatically</div>
    <div class="map-guide-save">✓ every change saves automatically — no save button needed</div>
  </div>`;

  const dropdown = `<select class="map-subtab-select" onchange="mapEditorPlaceId=this.value;renderWorldContent()">
    ${places.map(p=>`<option value="${esc(p.id)}"${p.id===sel?' selected':''}>${esc(p.emoji)} ${esc(p.name)}</option>`).join('')}
  </select>`;

  if(!sel) return guide + `<div style="color:var(--dimmer);font-size:.88em;padding:20px 0;text-align:center">no places yet — add a place in the places tab first</div>`;

  const map = getMapForPlace(sel);
  const place = places.find(p=>p.id===sel);

  if(!map){
    return `${guide}${dropdown}
      <div class="map-empty-hint">No map for <strong>${esc(place ? place.name : sel)}</strong> yet.<br>Click the button below to create one — you'll start with one room and can build from there.</div>
      <button class="world-add-btn" onclick="createMap('${esc(sel)}')">+ create map for ${esc(place ? place.name : sel)}</button>`;
  }

  const rooms = map.rooms || [];
  const roomCards = rooms.map((room, ri)=>{
    const isStart = map.startRoomId === room.id;
    const exits = room.exits || [];
    const beingsHere = (room.beings || []).map(bid=>{
      const b = getBeingById(bid);
      return b ? `${b.emoji} ${b.name}` : null;
    }).filter(Boolean).join(', ');

    const exitsHtml = exits.length
      ? `<div class="map-exits-section">
          <div class="map-exits-label">exits</div>
          ${exits.map((ex,ei)=>`<div class="map-exit-row">
            <span class="map-exit-label">${esc(ex.label)} → ${ex.roomId ? esc((rooms.find(r=>r.id===ex.roomId)||{}).name||'?') : '(exit map)'}</span>
            <button class="map-exit-del" onclick="deleteExit('${esc(map.id)}','${esc(room.id)}',${ei})" title="remove this exit">×</button>
          </div>`).join('')}
        </div>`
      : `<div class="map-no-exits">no exits yet — click "add exit" to connect this room to another</div>`;

    const editForm = mapRoomEditOpen[room.id] ? renderRoomEditForm(map, room) : '';
    const exitForm = mapExitFormOpen[room.id] ? renderAddExitForm(map, room) : '';

    return `<div class="map-room-card${isStart?' map-room-start':''}">
      <div class="map-room-head">
        <div class="map-room-number">${ri + 1}</div>
        <div class="map-room-emoji">${room.emoji||'🏠'}</div>
        <div class="map-room-name">${esc(room.name)}</div>
        ${isStart ? '<div class="map-room-star">★ start room</div>' : ''}
      </div>
      ${room.description
        ? `<div class="map-room-desc">${esc(room.description)}</div>`
        : `<div class="map-room-desc" style="opacity:.4;font-style:italic">no description yet — click edit to add one</div>`}
      ${beingsHere ? `<div style="font-size:.72em;color:var(--dimmer);margin-bottom:6px">beings here: ${beingsHere}</div>` : ''}
      ${exitsHtml}
      <div class="map-room-actions">
        <button class="world-action-btn" onclick="toggleRoomEdit('${esc(room.id)}')">${mapRoomEditOpen[room.id]?'done editing':'✏️ edit room'}</button>
        <button class="world-action-btn" onclick="toggleExitForm('${esc(room.id)}')">${mapExitFormOpen[room.id]?'cancel':'🚪 add exit'}</button>
        ${!isStart ? `<button class="world-action-btn" onclick="setStartRoom('${esc(map.id)}','${esc(room.id)}')" title="Players enter the map here">set as start</button>` : ''}
        ${rooms.length > 1 ? `<button class="world-action-btn del" onclick="deleteRoom('${esc(map.id)}','${esc(room.id)}')">delete</button>` : ''}
      </div>
      ${editForm}
      ${exitForm}
    </div>`;
  }).join('');

  return `${guide}
    ${dropdown}
    <div class="map-section-label">map for ${esc(place ? place.name : sel)} · ${rooms.length} room${rooms.length!==1?'s':''}</div>
    ${roomCards}
    <div class="map-bottom-actions">
      <button class="world-add-btn" onclick="addRoom('${esc(map.id)}')">+ add room</button>
      <button class="world-add-btn danger" onclick="if(confirm('Delete this entire map?'))deleteMap('${esc(map.id)}')">🗑 delete map</button>
    </div>`;
}

function renderRoomEditForm(map, room){
  const allBeings = S.world.beings;
  const beingChecks = allBeings.map(b=>`
    <label class="map-being-check">
      <input type="checkbox" ${(room.beings||[]).includes(b.id)?'checked':''}
        onchange="toggleBeingInRoom('${esc(map.id)}','${esc(room.id)}','${esc(b.id)}',this.checked)">
      ${b.emoji} ${esc(b.name)}
    </label>`).join('');

  return `<div class="map-room-edit-form">
    <div class="world-field">
      <label>Name</label>
      <input value="${esc(room.name)}" oninput="updateRoom('${esc(map.id)}','${esc(room.id)}','name',this.value)">
    </div>
    <div class="world-field">
      <label>Emoji</label>
      <input value="${esc(room.emoji||'')}" oninput="updateRoom('${esc(map.id)}','${esc(room.id)}','emoji',this.value)" maxlength="2" style="width:60px">
    </div>
    <div class="world-field">
      <label>Description</label>
      <textarea rows="2" oninput="updateRoom('${esc(map.id)}','${esc(room.id)}','description',this.value)">${esc(room.description||'')}</textarea>
    </div>
    <div class="world-field">
      <label>Beings present</label>
      <div class="map-beings-checks">${beingChecks}</div>
    </div>
  </div>`;
}

function renderAddExitForm(map, room){
  const rooms = map.rooms || [];
  const otherRooms = rooms.filter(r=>r.id!==room.id);
  return `<div class="map-add-exit-form">
    <div class="map-exit-hint">An exit is a door or path leading out of this room. Give it a label (what the player clicks) and pick where it goes.</div>
    <div class="world-field">
      <label>Exit label <span style="font-weight:400;opacity:.6">(what the player sees — e.g. "north", "up the stairs", "through the door")</span></label>
      <input id="exit-label-${esc(room.id)}" placeholder="north" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:7px;color:var(--text);padding:6px 8px;font-size:.82em;font-family:inherit;outline:none">
    </div>
    <div class="world-field">
      <label>Where does it lead? <span style="font-weight:400;opacity:.6">(pick a room, or "exit map" to leave entirely)</span></label>
      <select id="exit-dest-${esc(room.id)}" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:7px;color:var(--text);padding:6px 8px;font-size:.82em;font-family:inherit;outline:none">
        <option value="">↩ exit map (leave this location)</option>
        ${otherRooms.map(r=>`<option value="${esc(r.id)}">${esc(r.emoji||'🚪')} ${esc(r.name)}</option>`).join('')}
      </select>
    </div>
    <button class="world-action-btn confirm" onclick="addExit('${esc(map.id)}','${esc(room.id)}')">✓ save this exit</button>
  </div>`;
}

function createMap(placeId){
  const mapId = 'map_' + Date.now();
  const roomId = 'room_' + Date.now();
  const map = {
    id: mapId,
    placeId,
    rooms: [{
      id: roomId,
      name: 'Starting Room',
      emoji: '🚪',
      description: '',
      beings: [],
      exits: [],
      visited: false,
    }],
    startRoomId: roomId,
  };
  S.world.maps.push(map);
  save();
  renderWorldContent();
}

function deleteMap(mapId){
  S.world.maps = S.world.maps.filter(m=>m.id!==mapId);
  if(S.mapState && S.mapState.mapId === mapId) S.mapState = null;
  save();
  renderWorldContent();
}

function addRoom(mapId){
  const map = S.world.maps.find(m=>m.id===mapId);
  if(!map) return;
  const roomId = 'room_' + Date.now();
  map.rooms.push({ id:roomId, name:'New Room', emoji:'🚪', description:'', beings:[], exits:[], visited:false });
  mapRoomEditOpen[roomId] = true;
  save();
  renderWorldContent();
}

function deleteRoom(mapId, roomId){
  const map = S.world.maps.find(m=>m.id===mapId);
  if(!map) return;
  map.rooms = map.rooms.filter(r=>r.id!==roomId);
  // Remove exits pointing to this room
  map.rooms.forEach(r=>{ r.exits = r.exits.filter(ex=>ex.roomId!==roomId); });
  if(map.startRoomId === roomId) map.startRoomId = map.rooms[0] ? map.rooms[0].id : null;
  if(S.mapState && S.mapState.mapId===mapId && S.mapState.currentRoomId===roomId) S.mapState=null;
  save();
  renderWorldContent();
}

function updateRoom(mapId, roomId, field, value){
  const map = S.world.maps.find(m=>m.id===mapId);
  if(!map) return;
  const room = map.rooms.find(r=>r.id===roomId);
  if(room){ room[field] = value; save(); }
}

function setStartRoom(mapId, roomId){
  const map = S.world.maps.find(m=>m.id===mapId);
  if(map){ map.startRoomId = roomId; save(); renderWorldContent(); }
}

function toggleRoomEdit(roomId){
  mapRoomEditOpen[roomId] = !mapRoomEditOpen[roomId];
  mapExitFormOpen[roomId] = false;
  renderWorldContent();
}

function toggleExitForm(roomId){
  mapExitFormOpen[roomId] = !mapExitFormOpen[roomId];
  mapRoomEditOpen[roomId] = false;
  renderWorldContent();
}

function toggleBeingInRoom(mapId, roomId, beingId, checked){
  const map = S.world.maps.find(m=>m.id===mapId);
  if(!map) return;
  const room = map.rooms.find(r=>r.id===roomId);
  if(!room) return;
  if(!room.beings) room.beings = [];
  if(checked && !room.beings.includes(beingId)) room.beings.push(beingId);
  if(!checked) room.beings = room.beings.filter(id=>id!==beingId);
  save();
}

function addExit(mapId, roomId){
  const labelEl = document.getElementById(`exit-label-${roomId}`);
  const destEl  = document.getElementById(`exit-dest-${roomId}`);
  if(!labelEl || !destEl) return;
  const label = labelEl.value.trim();
  if(!label) return;
  const dest = destEl.value || null;
  const map = S.world.maps.find(m=>m.id===mapId);
  if(!map) return;
  const room = map.rooms.find(r=>r.id===roomId);
  if(!room) return;
  if(!room.exits) room.exits = [];
  room.exits.push({ label, roomId: dest || null });
  mapExitFormOpen[roomId] = false;
  save();
  renderWorldContent();
}

function deleteExit(mapId, roomId, exitIdx){
  const map = S.world.maps.find(m=>m.id===mapId);
  if(!map) return;
  const room = map.rooms.find(r=>r.id===roomId);
  if(!room || !room.exits) return;
  room.exits.splice(exitIdx, 1);
  save();
  renderWorldContent();
}

// ── Map Navigation ────────────────────────────────────────────────────────────

function enterMap(mapId){
  const map = S.world.maps.find(m=>m.id===mapId);
  if(!map) return;
  S.mapState = { mapId, currentRoomId: map.startRoomId };
  save();
  renderParty();
  renderMapNav();
}

function leaveMap(){
  S.mapState = null;
  save();
  renderParty();
  renderScene(getScene(S.currentSceneId));
}

function moveToRoom(roomId){
  if(!S.mapState) return;
  const map = S.world.maps.find(m=>m.id===S.mapState.mapId);
  if(!map) return;
  // Mark current room visited
  const cur = map.rooms.find(r=>r.id===S.mapState.currentRoomId);
  if(cur) cur.visited = true;
  S.mapState.currentRoomId = roomId;
  save();
  renderMapNav();
}

function renderMapNav(){
  const sa = document.getElementById('scene-area');
  const ca = document.getElementById('choices-area');
  if(!S.mapState){ renderScene(getScene(S.currentSceneId)); return; }

  const map = S.world.maps.find(m=>m.id===S.mapState.mapId);
  if(!map){ S.mapState=null; save(); renderScene(getScene(S.currentSceneId)); return; }

  const room = map.rooms.find(r=>r.id===S.mapState.currentRoomId);
  if(!room){ leaveMap(); return; }

  const beingNames = (room.beings||[]).map(bid=>{
    const b = getBeingById(bid);
    return b ? `${b.emoji} ${b.name}` : null;
  }).filter(Boolean).join(' · ');

  const minimapSvg = renderMinimap(map, S.mapState.currentRoomId);

  sa.innerHTML = `
    <div class="map-mode-indicator">map mode</div>
    ${minimapSvg}
    <div class="map-nav-room">
      <div class="map-nav-room-title">
        <span class="map-nav-room-emoji">${room.emoji||'🚪'}</span>
        <span>${esc(room.name)}</span>
      </div>
      ${room.description ? `<div class="map-nav-room-desc">${esc(room.description)}</div>` : ''}
      ${beingNames ? `<div class="map-nav-beings">beings here: ${beingNames}</div>` : ''}
    </div>`;

  const exits = room.exits || [];
  ca.innerHTML = exits.map((ex, i)=>{
    if(ex.roomId === null){
      return `<button class="map-exit-btn" onclick="leaveMap()">${esc(ex.label)} →</button>`;
    }
    return `<button class="map-exit-btn" onclick="moveToRoom('${esc(ex.roomId)}')">${esc(ex.label)} →</button>`;
  }).join('') + `<button class="map-leave-btn" onclick="leaveMap()">← leave map</button>`;
}

function renderMinimap(map, currentRoomId){
  const rooms = map.rooms || [];
  if(!rooms.length) return '';

  const W = 140, H = 100;
  const R = 13; // room circle radius
  const COLS = 3;

  // Assign grid positions via BFS from start room
  const posMap = {};
  const visited = new Set();
  const queue = [{ id: map.startRoomId, gx: 0, gy: 0 }];

  // direction keywords → grid offset
  function dirOffset(label){
    const l = label.toLowerCase();
    if(/north|up/.test(l))   return { dx:0, dy:-1 };
    if(/south|down/.test(l)) return { dx:0, dy:1 };
    if(/east|right/.test(l)) return { dx:1, dy:0 };
    if(/west|left/.test(l))  return { dx:-1, dy:0 };
    return null;
  }

  function freeCell(gx, gy){
    // Check if any room already occupies this cell
    for(const p of Object.values(posMap)){
      if(p.gx===gx && p.gy===gy) return false;
    }
    return true;
  }

  function nextFreeFrom(gx, gy){
    const offsets = [{dx:1,dy:0},{dx:-1,dy:0},{dx:0,dy:1},{dx:0,dy:-1},{dx:1,dy:1},{dx:-1,dy:1}];
    for(const {dx,dy} of offsets){
      if(freeCell(gx+dx, gy+dy)) return {gx:gx+dx, gy:gy+dy};
    }
    return {gx: gx+1, gy: gy};
  }

  // BFS layout
  while(queue.length){
    const {id, gx, gy} = queue.shift();
    if(visited.has(id)) continue;
    visited.add(id);
    const room = rooms.find(r=>r.id===id);
    if(!room) continue;
    if(!posMap[id]) posMap[id] = {gx, gy};
    const exits = room.exits||[];
    for(const ex of exits){
      if(!ex.roomId || visited.has(ex.roomId)) continue;
      const dir = dirOffset(ex.label);
      if(dir){
        const nx = gx + dir.dx, ny = gy + dir.dy;
        if(freeCell(nx,ny)){
          queue.push({ id: ex.roomId, gx: nx, gy: ny });
        } else {
          const nf = nextFreeFrom(gx, gy);
          queue.push({ id: ex.roomId, gx: nf.gx, gy: nf.gy });
        }
      } else {
        const nf = nextFreeFrom(gx, gy);
        queue.push({ id: ex.roomId, gx: nf.gx, gy: nf.gy });
      }
    }
  }
  // Fallback: any rooms not reached by BFS get grid positions
  rooms.forEach((room, i) => {
    if(!posMap[room.id]){
      const col = i % COLS, row = Math.floor(i / COLS);
      posMap[room.id] = { gx: col, gy: row };
    }
  });

  // Scale grid positions to SVG coords
  const gxs = Object.values(posMap).map(p=>p.gx);
  const gys = Object.values(posMap).map(p=>p.gy);
  const minGx = Math.min(...gxs), maxGx = Math.max(...gxs);
  const minGy = Math.min(...gys), maxGy = Math.max(...gys);
  const spanX = Math.max(maxGx - minGx, 1);
  const spanY = Math.max(maxGy - minGy, 1);
  const pad = R + 4;
  const cellW = (W - pad*2) / spanX;
  const cellH = (H - pad*2) / spanY;
  const cellSize = Math.min(cellW, cellH, 40);

  function toSvg(gx, gy){
    const cx = pad + (gx - minGx) * cellSize;
    const cy = pad + (gy - minGy) * cellSize;
    return { cx: Math.round(cx), cy: Math.round(cy) };
  }

  // Draw lines for connections
  const lines = [];
  const drawnEdges = new Set();
  rooms.forEach(room=>{
    const from = posMap[room.id];
    if(!from) return;
    const fp = toSvg(from.gx, from.gy);
    (room.exits||[]).forEach(ex=>{
      if(!ex.roomId) return;
      const edgeKey = [room.id, ex.roomId].sort().join('|');
      if(drawnEdges.has(edgeKey)) return;
      drawnEdges.add(edgeKey);
      const to = posMap[ex.roomId];
      if(!to) return;
      const tp = toSvg(to.gx, to.gy);
      lines.push(`<line x1="${fp.cx}" y1="${fp.cy}" x2="${tp.cx}" y2="${tp.cy}" stroke="#283040" stroke-width="2"/>`);
    });
  });

  // Draw circles for rooms
  const circles = rooms.map(room=>{
    const pos = posMap[room.id];
    if(!pos) return '';
    const {cx, cy} = toSvg(pos.gx, pos.gy);
    const isCurrent = room.id === currentRoomId;
    const isVisited = room.visited || room.id === map.startRoomId;
    const fillColor  = isCurrent ? '#2a2010' : '#141c28';
    const strokeColor= isCurrent ? '#d4b86a' : isVisited ? '#5a6878' : '#283040';
    const strokeW    = isCurrent ? 2 : 1.5;
    const pulse = isCurrent
      ? `<circle cx="${cx}" cy="${cy}" r="${R+3}" fill="none" stroke="#d4b86a" stroke-width="1" opacity="0.4"/>`
      : '';
    const emoji = room.emoji||'';
    return `${pulse}<circle cx="${cx}" cy="${cy}" r="${R}" fill="${fillColor}" stroke="${strokeColor}" stroke-width="${strokeW}"/>
      <text x="${cx}" y="${cy+5}" text-anchor="middle" font-size="12">${emoji}</text>`;
  }).join('');

  return `<svg class="map-minimap" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
    ${lines.join('')}
    ${circles}
  </svg>`;
}

// ── Realm Tab ─────────────────────────────────────────────────────────────────

function renderRealm(){
  const wc = document.getElementById('world-content');
  if(wc) wc.innerHTML = buildRealmHTML();
}

function buildRealmHTML(){
  const civ = S.world.civ;
  if(!civ) return '<div class="realm-locked">realm not initialized</div>';

  const eraName = ERA_NAMES[civ.era] || 'Unknown Era';
  const res = civ.resources;

  const resBar = `<div class="realm-resources">
    <div class="resource-chip">🪵 <span>${res.wood||0}</span></div>
    <div class="resource-chip">🪨 <span>${res.stone||0}</span></div>
    <div class="resource-chip">🌾 <span>${res.food||0}</span></div>
    <div class="resource-chip">💫 <span>${res.starlight||0}</span></div>
  </div>`;

  const availBuildings = CIV_BUILDINGS.filter(b => b.era <= civ.era);
  const lockedCount    = CIV_BUILDINGS.filter(b => b.era > civ.era).length;

  const buildingsHTML = availBuildings.map(b => {
    const built = civ.buildings.includes(b.id);
    const canAfford = !built && Object.entries(b.cost).every(([k,v]) => (res[k]||0) >= v);
    const costStr = Object.entries(b.cost).map(([k,v]) => `${v}${resIcon(k)}`).join(' ');
    return `<div class="building-card${built?' built':''}">
      <div class="building-head">
        <span class="building-emoji">${b.emoji}</span>
        <div class="building-info">
          <div class="building-name">${b.name}</div>
          <div class="building-desc">${b.desc}</div>
        </div>
        ${built
          ? `<div class="building-built-label">✓ built</div>`
          : `<button class="build-btn ${canAfford?'can-build':'no-funds'}" ${canAfford?`onclick="buildCivBuilding('${b.id}')"`:'disabled'}>
              <span class="build-cost">${costStr}</span>build
            </button>`}
      </div>
    </div>`;
  }).join('');

  const lockedNote = lockedCount > 0
    ? `<div class="realm-locked">${lockedCount} more structure${lockedCount===1?'':'s'} unlock as the grove grows</div>` : '';

  return `
    <div class="realm-era">
      <div class="realm-era-name">🌿 ${eraName}</div>
      <div class="realm-turn">chapter ${S.progress.chapter} · ${civ.totalTurns} turn${civ.totalTurns===1?'':'s'}</div>
    </div>
    ${resBar}
    ${buildCivMapHTML(civ)}
    <div class="realm-section-label">structures</div>
    <div class="realm-buildings">${buildingsHTML}</div>
    ${lockedNote}
    <div style="font-size:.62em;color:var(--dimmer);text-align:center;margin-top:14px;padding-bottom:8px;line-height:1.6">
      resources accumulate each chapter<br>structures provide permanent bonuses
    </div>`;
}

function buildCivMapHTML(civ){
  const places = S.world.places;

  const FIXED_POS = {
    grove:        {c:1, r:0},
    hearthside:   {c:0, r:1},
    crossroads:   {c:2, r:1},
    ruin_library: {c:0, r:2},
    makers_yard:  {c:2, r:2},
  };
  const TYPE_COLORS = {
    forest:'#0d2a18', tavern:'#2a1800', road:'#1a1a0a',
    ruins:'#1a1028',  workshop:'#1a0a00', custom:'#0a1420',
  };
  const TYPE_BORDER = {
    forest:'#2a5a30', tavern:'#5a2a00', road:'#3a3a18',
    ruins:'#2a1a48',  workshop:'#4a1a00', custom:'#283040',
  };

  const CUSTOM_POSES = [
    {c:0,r:3},{c:1,r:3},{c:2,r:3},{c:0,r:4},{c:1,r:4},{c:2,r:4},
  ];
  let customIdx = 0;

  let maxRow = 2;
  const placeWithPos = places.map(place => {
    let pos = FIXED_POS[place.id];
    if(!pos){
      pos = CUSTOM_POSES[customIdx] || {c:customIdx%3, r:3+Math.floor(customIdx/3)};
      customIdx++;
    }
    if(pos.r > maxRow) maxRow = pos.r;
    return {place, pos};
  });

  const tiles = placeWithPos.map(({place, pos}) => {
    const isCurrent = place.id === S.world.currentPlace;
    const yields    = getSettlementYield(place.id);
    const yieldIcons = Object.keys(yields).map(resIcon).join('');
    const bg  = TYPE_COLORS[place.type] || TYPE_COLORS.custom;
    const bdr = TYPE_BORDER[place.type] || TYPE_BORDER.custom;
    const shortName = place.name.replace(/^The /,'').substring(0, 11);
    return `<div class="civ-tile${isCurrent?' current':''}"
      style="grid-column:${pos.c+1};grid-row:${pos.r+1};background:${bg};border-color:${bdr}"
      onclick="travelTo('${esc(place.id)}')">
      <div class="civ-tile-emoji">${place.emoji}</div>
      <div class="civ-tile-name">${esc(shortName)}</div>
      <div class="civ-tile-yield">${yieldIcons}</div>
    </div>`;
  }).join('');

  return `<div class="civ-map" style="grid-template-rows:repeat(${maxRow+1},56px)">${tiles}</div>`;
}

// ── Memories Tab ──────────────────────────────────────────────────────────────

function renderMemories(){
  const mem = document.getElementById('mem');
  if(!S.memories.length){
    mem.innerHTML = `<div class="mem-header"><h2>memories</h2></div><div class="mem-empty">nothing yet</div>`;
    return;
  }
  const byChapter = {};
  for(const m of S.memories){
    if(!byChapter[m.chapter]) byChapter[m.chapter]=[]; byChapter[m.chapter].push(m);
  }
  mem.innerHTML = `
    <div class="mem-header">
      <h2>memories</h2>
      <button class="dl-btn" onclick="downloadMemories()">save .txt</button>
    </div>
    ${Object.entries(byChapter).reverse().map(([ch,mems])=>`
      <div class="mem-chapter">chapter ${ch} · day ${mems[0].day}</div>
      ${mems.map(m=>`
        <div class="mem-entry">
          <div class="mem-scene">${m.scene}</div>
          <div class="mem-text">${m.text}</div>
        </div>`).join('')}
    `).join('')}`;
}

function downloadMemories(){
  const lines = Object.entries(
    S.memories.reduce((acc,m)=>{(acc[m.chapter]=acc[m.chapter]||[]).push(m);return acc;},{})
  ).map(([ch,mems])=>`── Chapter ${ch} ──\n\n`+mems.map(m=>`${m.scene}\n${m.text}`).join('\n\n')).join('\n\n\n');
  const blob = new Blob([`${S.pucky.name} & ${S.loki.name} — Memories from the Grove\n\n${lines}`],{type:'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download=`${S.pucky.name}_memories.txt`; a.click();
  URL.revokeObjectURL(a.href);
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

function setTab(tab){
  ['adv','world','comp','mem'].forEach(t=>{
    const el = document.getElementById(t);
    const tabEl = document.getElementById(`tab-${t}`);
    if(el) el.classList.toggle('on', t===tab);
    if(tabEl) tabEl.classList.toggle('on', t===tab);
  });
  if(tab==='comp')  renderCompanions();
  if(tab==='mem')   renderMemories();
  if(tab==='world') renderWorld();
  if(tab==='adv'){
    renderParty();
    if(S.mapState){ renderMapNav(); } else { renderScene(getScene(S.currentSceneId)); }
  }
}

// ── Apple Touch Icon ──────────────────────────────────────────────────────────

(function(){
  const sz=180, c=document.createElement('canvas'); c.width=c.height=sz;
  const ctx=c.getContext('2d'), s=sz/512;
  ctx.fillStyle='#0a0e14'; ctx.fillRect(0,0,sz,sz);
  function glow(cx,cy,col){
    const g=ctx.createRadialGradient(cx,cy,0,cx,cy,110*s);
    g.addColorStop(0,col+'55'); g.addColorStop(1,col+'00');
    ctx.fillStyle=g; ctx.beginPath(); ctx.arc(cx,cy,110*s,0,Math.PI*2); ctx.fill();
  }
  function orb(cx,cy,l,m,d){
    const g=ctx.createRadialGradient(cx-10*s,cy-12*s,0,cx,cy,82*s);
    g.addColorStop(0,l); g.addColorStop(.48,m); g.addColorStop(1,d);
    ctx.fillStyle=g; ctx.beginPath(); ctx.arc(cx,cy,82*s,0,Math.PI*2); ctx.fill();
  }
  glow(168*s,256*s,'#68c88e'); glow(344*s,256*s,'#c8956a');
  orb(168*s,256*s,'#c0f8e0','#68c88e','#1a3f28');
  orb(344*s,256*s,'#f8e8c0','#c8956a','#3f2010');
  const lk=document.createElement('link'); lk.rel='apple-touch-icon';
  lk.href=c.toDataURL('image/png'); document.head.appendChild(lk);
})();

if('serviceWorker' in navigator) navigator.serviceWorker.register('./game-sw.js');

// ── Init ──────────────────────────────────────────────────────────────────────

S = mergeState(loadState());
if(!S.world || !S.world.beings){
  S.world = defaultWorld();
}
if(!S.world.maps) S.world.maps = [];
if(!S.world.civ)  S.world.civ  = defaultCiv();

// Clear any stale mid-combat state on cold load
if(S.combat && S.combat.preEncounter === undefined) S.combat = null;

renderParty();
initYellCheck();

if(S.combat){
  if(S.combat.preEncounter) renderCombatPreEncounter();
  else renderCombatScene();
} else if(S.mapState){
  renderMapNav();
} else {
  renderScene(getScene(S.currentSceneId));
}
