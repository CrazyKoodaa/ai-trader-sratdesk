//+------------------------------------------------------------------+
//|                XAU Velocity External Validation F7                       |
//|                                                                  |
//| XAUUSD Trend Expansion / Retracement Engine                      |
//| Adaptive Quality Routing                                         |
//| Frozen external validation build                                 |
//+------------------------------------------------------------------+
#property strict
#property version   "3.00"

#include <Trade/Trade.mqh>

CTrade trade;


//==================================================================
// ENUMS
//==================================================================

enum ManagementMode
{
   FTMO_F0_8R_LOCK_275R_075R = 0,
   FTMO_F1_8R_LOCK_275R_100R = 1,
   FTMO_F2_8R_LOCK_300R_075R = 2,
   FTMO_F3_8R_LOCK_300R_100R = 3, // current benchmark
   FTMO_F4_8R_LOCK_325R_075R = 4,
   FTMO_F5_8R_LOCK_325R_100R = 5,
   FTMO_F6_85R_LOCK_300R_100R = 6,
   FTMO_F7_85R_LOCK_325R_100R = 7
};


enum ChallengeType
{
   CHALLENGE_FTMO_2STEP = 0,
   CHALLENGE_FTMO_1STEP = 1
};


enum TradeDirection
{
   DIR_NONE  = 0,
   DIR_LONG  = 1,
   DIR_SHORT = -1
};


enum SignalQuality
{
   QUALITY_REJECT   = 0,
   QUALITY_STANDARD = 1,
   QUALITY_STRONG   = 2,
   QUALITY_ELITE    = 3
};


//==================================================================
// EXTERNAL VALIDATION CONFIGURATION
//==================================================================
//
// This build intentionally freezes the validated strategy settings.
// It is NOT a research/optimization build. The only exposed input is
// position risk so robustness/Monte-Carlo tests can scale sizing
// without changing the entry/management logic.
//==================================================================

input group "===== VALIDATION RISK ====="

input double RiskPct = 0.7;


// Frozen F7 management: TP 8.5R, lock at +3.25R to +1.0R.
const ManagementMode Management =
   FTMO_F7_85R_LOCK_325R_100R;


// Frozen session baseline.
const bool TradeAsia = true;
const bool TradeLondon = true;
const bool TradeNewYork = false;
const int FridayStopHour = 20;


// Frozen execution filters.
const int MaxSpreadPoints = 120;
const int MinMinutesBetweenEntries = 15;


// Challenge guards are deliberately disabled for external edge
// validation. FTMO rule logic is tested separately in dedicated builds.
const bool ChallengeMode = false;
const ChallengeType Challenge =
   CHALLENGE_FTMO_2STEP;


//==================================================================
// EA IDENTITY
//==================================================================

const string EA_NAME =
   "XAU Velocity External Validation F7";


const string SYMBOL_NAME =
   "XAUUSD";


const ulong MAGIC =
   26090801;


//==================================================================
// TIMEFRAMES
//==================================================================

const ENUM_TIMEFRAMES TF_CONTEXT =
   PERIOD_H4;


const ENUM_TIMEFRAMES TF_TREND =
   PERIOD_H1;


const ENUM_TIMEFRAMES TF_SETUP =
   PERIOD_M15;


const ENUM_TIMEFRAMES TF_ENTRY =
   PERIOD_M5;


//==================================================================
// INDICATORS
//==================================================================

const int EMA_FAST =
   20;


const int EMA_MID =
   50;


const int EMA_SLOW =
   200;


const int ATR_PERIOD =
   14;


const int ADX_PERIOD =
   14;


//==================================================================
// TREND REGIME
//
// V2.2:
// ADX >=20
// H1 EMA separation >=0.16 ATR
// H4 slope >=0.03 ATR
//
// We deliberately DO NOT raise ADX aggressively.
// V2.2 showed that low-but-valid ADX was not the weak cluster.
//==================================================================

const double MIN_TREND_ADX =
   20.0;


const double STRONG_TREND_ADX =
   27.0;


const double VERY_STRONG_TREND_ADX =
   34.0;


const double MIN_H1_EMA_SEPARATION_ATR =
   0.16;


const double STRONG_H1_EMA_SEPARATION_ATR =
   0.25;


const double MIN_H4_SLOPE_ATR =
   0.03;


const double STRONG_H4_SLOPE_ATR =
   0.08;


//==================================================================
// EXPANSION DETECTION
//
// Detection remains permissive.
//
// IMPORTANT:
// We detect impulses from 1.35x onward,
// but V2.3 does NOT automatically trade all of them.
//
// The Quality Router later decides whether the complete signal
// deserves execution.
//==================================================================

const int EXPANSION_LOOKBACK =
   8;


const double DETECT_MIN_EXPANSION_MULT =
   1.35;


const double DETECT_MIN_BODY_PCT =
   0.60;


//==================================================================
// V2.3 QUALITY LEVELS
//
// V2.2 research:
//
// weak expansion cluster:
// 1.35 - 1.50x was poor.
//
// >=1.50x improved substantially.
//
// Expansion >=1.50 + body >=0.68:
// PF approximately 1.49 in V2.2 sample.
//
// We use this information WITHOUT simply deleting every weaker
// expansion. Exceptional total-score signals may still qualify.
//==================================================================

const double QUALITY_EXPANSION_MULT =
   1.50;


const double STRONG_EXPANSION_MULT =
   1.80;


const double ELITE_EXPANSION_MULT =
   2.20;


const double QUALITY_BODY_PCT =
   0.68;


const double STRONG_BODY_PCT =
   0.75;


const double ELITE_BODY_PCT =
   0.82;


//==================================================================
// RETRACEMENT
//
// V2.3 keeps a broad detection window.
// Quality is graded inside that window.
//==================================================================

const double RETRACE_MIN_PCT =
   0.12;


const double RETRACE_MAX_PCT =
   0.62;


const double RETRACE_ACCEPTABLE_MIN =
   0.18;


const double RETRACE_ACCEPTABLE_MAX =
   0.55;


const double RETRACE_IDEAL_MIN =
   0.25;


const double RETRACE_IDEAL_MAX =
   0.48;


const double RETRACE_ELITE_MIN =
   0.32;


const double RETRACE_ELITE_MAX =
   0.42;


//==================================================================
// SETUP LIFE
//
// V2.2 showed:
//
// age 0 = strong
// age >0 = weak, but only 15 observations.
//
// Therefore V2.3 does NOT blindly delete delayed setups.
// Instead:
// - age 0 normal
// - delayed setups need stronger quality
//==================================================================

const int RETRACE_MAX_BARS =
   1;


const int DELAYED_SETUP_FROM_BAR =
   1;


//==================================================================
// INVALIDATION
//==================================================================

const double SETUP_INVALIDATION_ATR =
   0.12;


//==================================================================
// MANAGEMENT
//==================================================================

double SelectedTPR()
{
   if(Management == FTMO_F6_85R_LOCK_300R_100R ||
      Management == FTMO_F7_85R_LOCK_325R_100R)
      return 8.5;

   return 8.0;
}

#define TP_R SelectedTPR()


double SelectedLockTriggerR()
{
   if(Management == FTMO_F0_8R_LOCK_275R_075R ||
      Management == FTMO_F1_8R_LOCK_275R_100R)
      return 2.75;

   if(Management == FTMO_F4_8R_LOCK_325R_075R ||
      Management == FTMO_F5_8R_LOCK_325R_100R ||
      Management == FTMO_F7_85R_LOCK_325R_100R)
      return 3.25;

   return 3.0;
}


double SelectedLockSLR()
{
   if(Management == FTMO_F0_8R_LOCK_275R_075R ||
      Management == FTMO_F2_8R_LOCK_300R_075R ||
      Management == FTMO_F4_8R_LOCK_325R_075R)
      return 0.75;

   return 1.0;
}

#define LOCK_TRIGGER_R SelectedLockTriggerR()
#define LOCK_SL_R      SelectedLockSLR()


//==================================================================
// V2.3 ADAPTIVE SCORE ROUTER
//
// Key change:
//
// V2.2 had one global MinScore.
//
// V2.3 asks:
// "How much confirmation is required given the raw quality of
//  the expansion?"
//
// A mediocre impulse requires a very strong overall score.
// A structurally strong impulse does not need score inflation.
//==================================================================

const int SCORE_ABSOLUTE_MIN =
   72;


const int SCORE_STANDARD_MIN =
   84;


const int SCORE_STRONG_MIN =
   78;


const int SCORE_ELITE_MIN =
   72;


const int SCORE_EXCEPTIONAL =
   92;


//==================================================================
// DELAYED SETUP PROTECTION
//
// A setup entering after its first bar must be clearly above average.
//==================================================================

const int DELAYED_SETUP_MIN_SCORE =
   88;


const double DELAYED_SETUP_MIN_EXPANSION =
   1.60;


const double DELAYED_SETUP_MIN_BODY =
   0.70;


//==================================================================
// SESSION QUALITY
//
// We keep both sessions.
//
// V2.2:
// Asia was stronger.
// London remained profitable.
//
// Therefore London is NOT disabled.
// It receives slightly stricter quality treatment later.
//==================================================================

const int ASIA_SCORE_BONUS =
   9;


const int LONDON_SCORE_BONUS =
   6;


const int NEWYORK_SCORE_BONUS =
   2;


//==================================================================
// LONDON QUALITY CONTROL
//==================================================================

const int LONDON_MIN_SCORE =
   76;


const double LONDON_MIN_EXPANSION =
   1.45;


//==================================================================
// DIRECTION
//
// Both directions remain enabled.
//
// V2.2 SELL was stronger, but BUY remained profitable.
// Direction is therefore a score/context factor,
// NOT a hard BUY/SELL switch.
//==================================================================

const int SELL_QUALITY_BONUS =
   2;


const int BUY_QUALITY_BONUS =
   0;


//==================================================================
// FREQUENCY
//==================================================================

const int MAX_POSITIONS =
   1;


const int MAX_ENTRIES_PER_HOUR =
   3;


//==================================================================
// CHALLENGE RESEARCH SAFETY
//
// Still only research protection.
// Final FTMO implementation comes after the strategy itself is
// considered production/live capable.
//==================================================================

const double FTMO_2STEP_DAILY_STOP =
   4.0;


const double FTMO_2STEP_TOTAL_STOP =
   8.0;


const double FTMO_1STEP_DAILY_STOP =
   2.3;


const double FTMO_1STEP_TOTAL_STOP =
   8.0;


//==================================================================
// TRADE SIGNAL
//==================================================================

struct TradeSignal
{
   bool valid;

   TradeDirection direction;

   SignalQuality quality;


   // ---------------------------------------------------------------
   // EXECUTION
   // ---------------------------------------------------------------

   double entry;

   double sl;

   double tp;

   double risk_distance;


   // ---------------------------------------------------------------
   // MARKET STATE
   // ---------------------------------------------------------------

   double atr;

   double adx;

   double plus_di;

   double minus_di;


   // ---------------------------------------------------------------
   // EXPANSION
   // ---------------------------------------------------------------

   datetime expansion_time;

   double expansion_high;

   double expansion_low;

   double expansion_open;

   double expansion_close;

   double expansion_range;

   double expansion_body_pct;

   double expansion_multiple;


   // ---------------------------------------------------------------
   // RETRACEMENT
   // ---------------------------------------------------------------

   double retrace_pct;

   int setup_age_bars;


   // ---------------------------------------------------------------
   // FVG
   // ---------------------------------------------------------------

   bool fvg_present;

   bool inside_fvg;

   double fvg_low;

   double fvg_high;


   // ---------------------------------------------------------------
   // SCORE
   // ---------------------------------------------------------------

   int score;

   int required_score;

   int score_regime;

   int score_htf;

   int score_expansion;

   int score_structure;

   int score_retrace;

   int score_session;

   int score_direction;

   int score_quality;


   // ---------------------------------------------------------------
   // CONTEXT
   // ---------------------------------------------------------------

   string session;

   string reason;
};


//==================================================================
// PERSISTENT EXPANSION SETUP
//==================================================================

struct ExpansionSetup
{
   bool active;

   TradeDirection direction;


   // ---------------------------------------------------------------
   // TIME
   // ---------------------------------------------------------------

   datetime expansion_time;

   datetime armed_time;

   datetime expiry_time;

   int bars_alive;


   // ---------------------------------------------------------------
   // EXPANSION
   // ---------------------------------------------------------------

   double expansion_high;

   double expansion_low;

   double expansion_open;

   double expansion_close;

   double expansion_range;

   double body_pct;

   double average_range;

   double range_multiple;


   // ---------------------------------------------------------------
   // MARKET CONTEXT AT ARM
   // ---------------------------------------------------------------

   double atr;

   double adx;

   double plus_di;

   double minus_di;


   // ---------------------------------------------------------------
   // BREAKOUT REFERENCE
   // ---------------------------------------------------------------

   double prior_high;

   double prior_low;


   // ---------------------------------------------------------------
   // INVALIDATION
   // ---------------------------------------------------------------

   double invalidation_price;


   // ---------------------------------------------------------------
   // FVG
   // ---------------------------------------------------------------

   bool fvg_present;

   double fvg_low;

   double fvg_high;


   // ---------------------------------------------------------------
   // BASE SCORES
   // ---------------------------------------------------------------

   int base_regime_score;

   int base_htf_score;

   int base_expansion_score;

   int base_structure_score;

   int base_session_score;

   int base_direction_score;


   string session;
};


ExpansionSetup setup;


//==================================================================
// POSITION STATE
//
// Complete signal metadata stays attached to the position until
// FINAL_CLOSE.
//
// This is essential for V2.3 research.
//==================================================================

struct PositionState
{
   ulong ticket;

   ulong position_id;

   TradeDirection direction;

   SignalQuality quality;


   // ---------------------------------------------------------------
   // POSITION
   // ---------------------------------------------------------------

   datetime open_time;

   double volume;

   double entry;

   double initial_sl;

   double initial_tp;

   double risk_distance;

   double initial_risk_money;


   // ---------------------------------------------------------------
   // EXCURSION
   // ---------------------------------------------------------------

   double max_r;

   double min_r;


   // ---------------------------------------------------------------
   // MANAGEMENT
   // ---------------------------------------------------------------

   bool lock_done;

   bool lock_attempted;


   // ---------------------------------------------------------------
   // SIGNAL CONTEXT
   // ---------------------------------------------------------------

   string session;

   int score;

   int required_score;

   int score_regime;

   int score_htf;

   int score_expansion;

   int score_structure;

   int score_retrace;

   int score_session;

   int score_direction;

   int score_quality;


   // ---------------------------------------------------------------
   // INDICATORS
   // ---------------------------------------------------------------

   double signal_atr;

   double signal_adx;

   double signal_plus_di;

   double signal_minus_di;


   // ---------------------------------------------------------------
   // EXPANSION
   // ---------------------------------------------------------------

   datetime expansion_time;

   double expansion_range;

   double expansion_body_pct;

   double expansion_multiple;


   // ---------------------------------------------------------------
   // RETRACEMENT
   // ---------------------------------------------------------------

   double retrace_pct;

   int setup_age_bars;


   // ---------------------------------------------------------------
   // FVG
   // ---------------------------------------------------------------

   bool fvg_present;

   bool inside_fvg;

   double fvg_low;

   double fvg_high;


   string entry_reason;
};


PositionState states[];


//==================================================================
// PENDING ENTRY
//
// Preserves the complete signal while CTrade / OnTradeTransaction
// processes the market order.
//==================================================================

TradeSignal pending_entry_signal;

bool pending_entry_signal_valid =
   false;


//==================================================================
// GLOBAL STATE
//==================================================================

datetime last_entry_time =
   0;


datetime entry_times[];


datetime last_m5_bar =
   0;


double account_start_equity =
   0.0;


double day_start_equity =
   0.0;


int current_day_key =
   0;


//==================================================================
// FILES
//==================================================================

const string TRADE_CSV =
   "XAU_Velocity_EXTERNAL_VALIDATION_F7_Trades.csv";


const string DIAG_CSV =
   "XAU_Velocity_EXTERNAL_VALIDATION_F7_Diagnostics.csv";


int trade_file =
   INVALID_HANDLE;


int diag_file =
   INVALID_HANDLE;


//==================================================================
// SYMBOL HELPERS
//==================================================================

double PointValue()
{
   return SymbolInfoDouble(
      SYMBOL_NAME,
      SYMBOL_POINT
   );
}


int DigitsValue()
{
   return (int)
      SymbolInfoInteger(
         SYMBOL_NAME,
         SYMBOL_DIGITS
      );
}


double TickSize()
{
   double value =
      SymbolInfoDouble(
         SYMBOL_NAME,
         SYMBOL_TRADE_TICK_SIZE
      );


   if(
      value <= 0.0
   )
   {
      value =
         PointValue();
   }


   return value;
}


//==================================================================
// NORMALIZE PRICE
//==================================================================

double NormalizePrice(
   double price
)
{
   double tick_size =
      TickSize();


   if(
      tick_size <= 0.0
   )
      return price;


   double result =
      MathRound(
         price /
         tick_size
      )
      *
      tick_size;


   return NormalizeDouble(
      result,
      DigitsValue()
   );
}


//==================================================================
// NORMALIZE VOLUME
//==================================================================

double NormalizeVolume(
   double volume
)
{
   double minimum =
      SymbolInfoDouble(
         SYMBOL_NAME,
         SYMBOL_VOLUME_MIN
      );


   double maximum =
      SymbolInfoDouble(
         SYMBOL_NAME,
         SYMBOL_VOLUME_MAX
      );


   double step =
      SymbolInfoDouble(
         SYMBOL_NAME,
         SYMBOL_VOLUME_STEP
      );


   if(
      step <= 0.0
   )
      return 0.0;


   volume =
      MathFloor(
         volume /
         step
      )
      *
      step;


   if(
      volume <
      minimum
   )
      return 0.0;


   if(
      volume >
      maximum
   )
   {
      volume =
         maximum;
   }


   return NormalizeDouble(
      volume,
      8
   );
}


//==================================================================
// CURRENT TICK
//==================================================================

bool GetCurrentTick(
   MqlTick &tick
)
{
   if(
      !SymbolInfoTick(
         SYMBOL_NAME,
         tick
      )
   )
      return false;


   if(
      tick.bid <= 0.0 ||
      tick.ask <= 0.0
   )
      return false;


   return true;
}


//==================================================================
// RATES
//==================================================================

bool GetRatesData(
   ENUM_TIMEFRAMES timeframe,
   int shift,
   int count,
   MqlRates &rates[]
)
{
   ArrayFree(
      rates
   );


   ArraySetAsSeries(
      rates,
      true
   );


   int copied =
      CopyRates(
         SYMBOL_NAME,
         timeframe,
         shift,
         count,
         rates
      );


   return (
      copied ==
      count
   );
}


//==================================================================
// CANDLE HELPERS
//==================================================================

double CandleRange(
   MqlRates &bar
)
{
   return (
      bar.high -
      bar.low
   );
}


double CandleBody(
   MqlRates &bar
)
{
   return MathAbs(
      bar.close -
      bar.open
   );
}


bool Bullish(
   MqlRates &bar
)
{
   return (
      bar.close >
      bar.open
   );
}


bool Bearish(
   MqlRates &bar
)
{
   return (
      bar.close <
      bar.open
   );
}


//==================================================================
// HIGHEST HIGH
//==================================================================

double HighestHigh(
   MqlRates &rates[],
   int start,
   int count
)
{
   double value =
      -DBL_MAX;


   int size =
      ArraySize(
         rates
      );


   int end =
      MathMin(
         start + count,
         size
      );


   for(
      int i = start;
      i < end;
      i++
   )
   {
      if(
         rates[i].high >
         value
      )
      {
         value =
            rates[i].high;
      }
   }


   return value;
}


//==================================================================
// LOWEST LOW
//==================================================================

double LowestLow(
   MqlRates &rates[],
   int start,
   int count
)
{
   double value =
      DBL_MAX;


   int size =
      ArraySize(
         rates
      );


   int end =
      MathMin(
         start + count,
         size
      );


   for(
      int i = start;
      i < end;
      i++
   )
   {
      if(
         rates[i].low <
         value
      )
      {
         value =
            rates[i].low;
      }
   }


   return value;
}


//==================================================================
// INDICATOR BUFFER
//==================================================================

bool ReadIndicator(
   int handle,
   int buffer,
   int shift,
   double &value
)
{
   if(
      handle ==
      INVALID_HANDLE
   )
      return false;


   double data[];

   ArraySetAsSeries(
      data,
      true
   );


   int copied =
      CopyBuffer(
         handle,
         buffer,
         shift,
         1,
         data
      );


   if(
      copied != 1
   )
      return false;


   value =
      data[0];


   return true;
}


//==================================================================
// EMA
//==================================================================

bool GetEMA(
   ENUM_TIMEFRAMES timeframe,
   int period,
   int shift,
   double &value
)
{
   int handle =
      iMA(
         SYMBOL_NAME,
         timeframe,
         period,
         0,
         MODE_EMA,
         PRICE_CLOSE
      );


   if(
      handle ==
      INVALID_HANDLE
   )
      return false;


   bool result =
      ReadIndicator(
         handle,
         0,
         shift,
         value
      );


   IndicatorRelease(
      handle
   );


   return result;
}


//==================================================================
// ATR
//==================================================================

bool GetATR(
   ENUM_TIMEFRAMES timeframe,
   int shift,
   double &value
)
{
   int handle =
      iATR(
         SYMBOL_NAME,
         timeframe,
         ATR_PERIOD
      );


   if(
      handle ==
      INVALID_HANDLE
   )
      return false;


   bool result =
      ReadIndicator(
         handle,
         0,
         shift,
         value
      );


   IndicatorRelease(
      handle
   );


   return result;
}


//==================================================================
// ADX + DI
//==================================================================

bool GetADX(
   ENUM_TIMEFRAMES timeframe,
   int shift,
   double &adx,
   double &plus_di,
   double &minus_di
)
{
   int handle =
      iADX(
         SYMBOL_NAME,
         timeframe,
         ADX_PERIOD
      );


   if(
      handle ==
      INVALID_HANDLE
   )
      return false;


   bool a =
      ReadIndicator(
         handle,
         0,
         shift,
         adx
      );


   bool b =
      ReadIndicator(
         handle,
         1,
         shift,
         plus_di
      );


   bool c =
      ReadIndicator(
         handle,
         2,
         shift,
         minus_di
      );


   IndicatorRelease(
      handle
   );


   return (
      a &&
      b &&
      c
   );
}


//==================================================================
// SESSION
//==================================================================

string CurrentSession()
{
   MqlDateTime dt;


   TimeToStruct(
      TimeCurrent(),
      dt
   );


   if(
      dt.hour >= 0 &&
      dt.hour < 7
   )
      return "Asia";


   if(
      dt.hour >= 7 &&
      dt.hour < 13
   )
      return "London";


   if(
      dt.hour >= 13 &&
      dt.hour < 21
   )
      return "NewYork";


   return "Late";
}


//==================================================================
// SESSION ALLOWED
//==================================================================

bool SessionAllowed()
{
   string session =
      CurrentSession();


   if(
      session ==
      "Asia"
   )
      return TradeAsia;


   if(
      session ==
      "London"
   )
      return TradeLondon;


   if(
      session ==
      "NewYork"
   )
      return TradeNewYork;


   return false;
}


//==================================================================
// FRIDAY FILTER
//==================================================================

bool FridayAllowed()
{
   MqlDateTime dt;


   TimeToStruct(
      TimeCurrent(),
      dt
   );


   if(
      dt.day_of_week == 5 &&
      dt.hour >= FridayStopHour
   )
      return false;


   return true;
}


//==================================================================
// SPREAD
//==================================================================

double CurrentSpreadPoints()
{
   MqlTick tick;


   if(
      !GetCurrentTick(
         tick
      )
   )
      return DBL_MAX;


   double point =
      PointValue();


   if(
      point <= 0.0
   )
      return DBL_MAX;


   return (
      tick.ask -
      tick.bid
   )
   /
   point;
}


bool SpreadAllowed()
{
   return (
      CurrentSpreadPoints()
      <=
      MaxSpreadPoints
   );
}


//==================================================================
// BROKER MINIMUM STOP DISTANCE
//==================================================================

double BrokerMinStopDistance()
{
   long stops =
      SymbolInfoInteger(
         SYMBOL_NAME,
         SYMBOL_TRADE_STOPS_LEVEL
      );


   long freeze =
      SymbolInfoInteger(
         SYMBOL_NAME,
         SYMBOL_TRADE_FREEZE_LEVEL
      );


   long level =
      MathMax(
         stops,
         freeze
      );


   return (
      (double)level *
      PointValue()
   );
}


//==================================================================
// STOP VALIDATION
//==================================================================

bool StopsValid(
   TradeDirection direction,
   double entry,
   double sl,
   double tp
)
{
   double minimum =
      BrokerMinStopDistance();


   if(
      direction ==
      DIR_LONG
   )
   {
      if(
         sl >= entry ||
         tp <= entry
      )
         return false;


      if(
         entry - sl <
         minimum
      )
         return false;


      if(
         tp - entry <
         minimum
      )
         return false;
   }


   if(
      direction ==
      DIR_SHORT
   )
   {
      if(
         sl <= entry ||
         tp >= entry
      )
         return false;


      if(
         sl - entry <
         minimum
      )
         return false;


      if(
         entry - tp <
         minimum
      )
         return false;
   }


   return true;
}


//==================================================================
// EMPTY SIGNAL
//==================================================================

TradeSignal EmptySignal()
{
   TradeSignal signal;


   ZeroMemory(
      signal
   );


   signal.valid =
      false;


   signal.direction =
      DIR_NONE;


   signal.quality =
      QUALITY_REJECT;


   signal.required_score =
      999;


   signal.session =
      CurrentSession();


   signal.reason =
      "";


   return signal;
}


//==================================================================
// RESET PENDING SIGNAL
//==================================================================

void ResetPendingSignal()
{
   pending_entry_signal =
      EmptySignal();


   pending_entry_signal_valid =
      false;
}


//==================================================================
// RESET SETUP
//==================================================================

void ResetSetup()
{
   ZeroMemory(
      setup
   );


   setup.active =
      false;


   setup.direction =
      DIR_NONE;
}


//==================================================================
// DAY KEY
//==================================================================

int DayKey()
{
   MqlDateTime dt;


   TimeToStruct(
      TimeCurrent(),
      dt
   );


   return (
      dt.year *
      10000
      +
      dt.mon *
      100
      +
      dt.day
   );
}


//==================================================================
// DAILY BASELINE
//==================================================================

void UpdateDayBaseline()
{
   int key =
      DayKey();


   if(
      key !=
      current_day_key
   )
   {
      current_day_key =
         key;


      day_start_equity =
         AccountInfoDouble(
            ACCOUNT_EQUITY
         );
   }
}


//==================================================================
// CHALLENGE LIMITS
//==================================================================

double ChallengeDailyStopPct()
{
   if(
      Challenge ==
      CHALLENGE_FTMO_1STEP
   )
      return FTMO_1STEP_DAILY_STOP;


   return FTMO_2STEP_DAILY_STOP;
}


double ChallengeTotalStopPct()
{
   if(
      Challenge ==
      CHALLENGE_FTMO_1STEP
   )
      return FTMO_1STEP_TOTAL_STOP;


   return FTMO_2STEP_TOTAL_STOP;
}


//==================================================================
// CHALLENGE ENTRY PROTECTION
//==================================================================

bool ChallengeAllowsTrading()
{
   if(
      !ChallengeMode
   )
      return true;


   double equity =
      AccountInfoDouble(
         ACCOUNT_EQUITY
      );


   if(
      account_start_equity <= 0.0 ||
      day_start_equity <= 0.0
   )
      return false;


   double total_loss_pct =
      (
         account_start_equity -
         equity
      )
      /
      account_start_equity
      *
      100.0;


   double daily_loss_pct =
      (
         day_start_equity -
         equity
      )
      /
      day_start_equity
      *
      100.0;


   if(
      total_loss_pct >=
      ChallengeTotalStopPct()
   )
      return false;


   if(
      daily_loss_pct >=
      ChallengeDailyStopPct()
   )
      return false;


   return true;
}


//==================================================================
// LOSS PER LOT
//==================================================================

double LossPerLot(
   TradeDirection direction,
   double entry,
   double sl
)
{
   ENUM_ORDER_TYPE order_type;


   if(
      direction ==
      DIR_LONG
   )
   {
      order_type =
         ORDER_TYPE_BUY;
   }
   else
   {
      order_type =
         ORDER_TYPE_SELL;
   }


   double profit =
      0.0;


   if(
      !OrderCalcProfit(
         order_type,
         SYMBOL_NAME,
         1.0,
         entry,
         sl,
         profit
      )
   )
      return 0.0;


   return MathAbs(
      profit
   );
}


//==================================================================
// POSITION SIZE
//==================================================================

double CalculateVolume(
   TradeDirection direction,
   double entry,
   double sl,
   double &risk_money
)
{
   double equity =
      AccountInfoDouble(
         ACCOUNT_EQUITY
      );


   if(
      equity <= 0.0
   )
      return 0.0;


   risk_money =
      equity *
      RiskPct /
      100.0;


   double loss_per_lot =
      LossPerLot(
         direction,
         entry,
         sl
      );


   if(
      loss_per_lot <= 0.0
   )
      return 0.0;


   double volume =
      risk_money /
      loss_per_lot;


   return NormalizeVolume(
      volume
   );
}


//==================================================================
// BOT POSITION COUNT
//==================================================================

int BotPositionCount()
{
   int count =
      0;


   for(
      int i =
      PositionsTotal() - 1;
      i >= 0;
      i--
   )
   {
      ulong ticket =
         PositionGetTicket(
            i
         );


      if(
         ticket == 0
      )
         continue;


      if(
         !PositionSelectByTicket(
            ticket
         )
      )
         continue;


      if(
         PositionGetString(
            POSITION_SYMBOL
         )
         !=
         SYMBOL_NAME
      )
         continue;


      if(
         PositionGetInteger(
            POSITION_MAGIC
         )
         !=
         (long)MAGIC
      )
         continue;


      count++;
   }


   return count;
}


//==================================================================
// ENTRY TIMES
//==================================================================

void CleanEntryTimes()
{
   datetime cutoff =
      TimeCurrent() -
      3600;


   int write_index =
      0;


   for(
      int i = 0;
      i < ArraySize(entry_times);
      i++
   )
   {
      if(
         entry_times[i] >=
         cutoff
      )
      {
         entry_times[
            write_index
         ] =
            entry_times[i];


         write_index++;
      }
   }


   ArrayResize(
      entry_times,
      write_index
   );
}


//==================================================================
// FREQUENCY ALLOWED
//==================================================================

bool FrequencyAllowed()
{
   if(
      last_entry_time > 0
   )
   {
      if(
         TimeCurrent() -
         last_entry_time
         <
         MinMinutesBetweenEntries *
         60
      )
      {
         return false;
      }
   }


   CleanEntryTimes();


   if(
      ArraySize(
         entry_times
      )
      >=
      MAX_ENTRIES_PER_HOUR
   )
      return false;


   return true;
}


//==================================================================
// REGISTER ENTRY TIME
//==================================================================

void RegisterEntryTime()
{
   last_entry_time =
      TimeCurrent();


   int size =
      ArraySize(
         entry_times
      );


   ArrayResize(
      entry_times,
      size + 1
   );


   entry_times[size] =
      TimeCurrent();
}


//==================================================================
// GLOBAL ENTRY FILTER
//==================================================================

bool GlobalEntryAllowed()
{
   if(
      !SessionAllowed()
   )
      return false;


   if(
      !FridayAllowed()
   )
      return false;


   if(
      !SpreadAllowed()
   )
      return false;


   if(
      !ChallengeAllowsTrading()
   )
      return false;


   if(
      BotPositionCount()
      >=
      MAX_POSITIONS
   )
      return false;


   if(
      !FrequencyAllowed()
   )
      return false;


   return true;
}


//==================================================================
// NEW M5 BAR
//==================================================================

bool IsNewM5Bar()
{
   datetime bar_time =
      iTime(
         SYMBOL_NAME,
         TF_ENTRY,
         0
      );


   if(
      bar_time <= 0
   )
      return false;


   if(
      bar_time ==
      last_m5_bar
   )
      return false;


   last_m5_bar =
      bar_time;


   return true;
}


//==================================================================
// QUALITY NAME
//==================================================================

string QualityName(
   SignalQuality quality
)
{
   if(
      quality ==
      QUALITY_ELITE
   )
      return "ELITE";


   if(
      quality ==
      QUALITY_STRONG
   )
      return "STRONG";


   if(
      quality ==
      QUALITY_STANDARD
   )
      return "STANDARD";


   return "REJECT";
}


//==================================================================
// END PART 1
//==================================================================//==================================================================
// PART 2
// TREND REGIME + EXPANSION + V2.3 QUALITY ROUTER
//==================================================================


//==================================================================
// H1 TREND DIRECTION
//==================================================================

TradeDirection TrendDirectionH1(
   double &ema_fast,
   double &ema_mid,
   double &ema_slow,
   double &atr,
   double &separation_atr
)
{
   ema_fast       = 0.0;
   ema_mid        = 0.0;
   ema_slow       = 0.0;
   atr            = 0.0;
   separation_atr = 0.0;


   if(
      !GetEMA(
         TF_TREND,
         EMA_FAST,
         1,
         ema_fast
      )
   )
      return DIR_NONE;


   if(
      !GetEMA(
         TF_TREND,
         EMA_MID,
         1,
         ema_mid
      )
   )
      return DIR_NONE;


   if(
      !GetEMA(
         TF_TREND,
         EMA_SLOW,
         1,
         ema_slow
      )
   )
      return DIR_NONE;


   if(
      !GetATR(
         TF_TREND,
         1,
         atr
      )
   )
      return DIR_NONE;


   if(
      atr <= 0.0
   )
      return DIR_NONE;


   separation_atr =
      MathAbs(
         ema_fast -
         ema_mid
      )
      /
      atr;


   if(
      separation_atr <
      MIN_H1_EMA_SEPARATION_ATR
   )
      return DIR_NONE;


   if(
      ema_fast >
      ema_mid
      &&
      ema_mid >
      ema_slow
   )
      return DIR_LONG;


   if(
      ema_fast <
      ema_mid
      &&
      ema_mid <
      ema_slow
   )
      return DIR_SHORT;


   return DIR_NONE;
}


//==================================================================
// H4 TREND DIRECTION
//==================================================================

TradeDirection TrendDirectionH4(
   double &ema_mid,
   double &ema_slow,
   double &atr,
   double &slope_atr
)
{
   ema_mid   = 0.0;
   ema_slow  = 0.0;
   atr       = 0.0;
   slope_atr = 0.0;


   double ema_mid_old =
      0.0;


   if(
      !GetEMA(
         TF_CONTEXT,
         EMA_MID,
         1,
         ema_mid
      )
   )
      return DIR_NONE;


   if(
      !GetEMA(
         TF_CONTEXT,
         EMA_MID,
         3,
         ema_mid_old
      )
   )
      return DIR_NONE;


   if(
      !GetEMA(
         TF_CONTEXT,
         EMA_SLOW,
         1,
         ema_slow
      )
   )
      return DIR_NONE;


   if(
      !GetATR(
         TF_CONTEXT,
         1,
         atr
      )
   )
      return DIR_NONE;


   if(
      atr <= 0.0
   )
      return DIR_NONE;


   slope_atr =
      (
         ema_mid -
         ema_mid_old
      )
      /
      atr;


   if(
      ema_mid >
      ema_slow
      &&
      slope_atr >=
      MIN_H4_SLOPE_ATR
   )
      return DIR_LONG;


   if(
      ema_mid <
      ema_slow
      &&
      slope_atr <=
      -MIN_H4_SLOPE_ATR
   )
      return DIR_SHORT;


   return DIR_NONE;
}


//==================================================================
// M15 STRUCTURE
//==================================================================

bool M15StructureAligned(
   TradeDirection direction
)
{
   MqlRates rates[];


   if(
      !GetRatesData(
         TF_SETUP,
         1,
         10,
         rates
      )
   )
      return false;


   double recent_high =
      HighestHigh(
         rates,
         0,
         5
      );


   double recent_low =
      LowestLow(
         rates,
         0,
         5
      );


   double older_high =
      HighestHigh(
         rates,
         5,
         5
      );


   double older_low =
      LowestLow(
         rates,
         5,
         5
      );


   if(
      direction ==
      DIR_LONG
   )
   {
      return (
         recent_high >
         older_high
         &&
         recent_low >=
         older_low
      );
   }


   if(
      direction ==
      DIR_SHORT
   )
   {
      return (
         recent_low <
         older_low
         &&
         recent_high <=
         older_high
      );
   }


   return false;
}


//==================================================================
// TREND REGIME
//
// Hard requirements:
// H1 aligned
// H4 aligned
// H1/H4 same direction
// M15 ADX >= 20
// DI broadly supports direction
//
// M15 structure remains SOFT.
// V2.2 showed little justification for making it a hard filter.
//==================================================================

bool StrongTrendRegime(
   TradeDirection &direction,

   double &adx,
   double &plus_di,
   double &minus_di,

   double &h1_separation_atr,
   double &h4_slope_atr,

   int &regime_score,
   int &htf_score,
   int &structure_score
)
{
   direction =
      DIR_NONE;


   adx =
      0.0;


   plus_di =
      0.0;


   minus_di =
      0.0;


   h1_separation_atr =
      0.0;


   h4_slope_atr =
      0.0;


   regime_score =
      0;


   htf_score =
      0;


   structure_score =
      0;


   //===============================================================
   // H1
   //===============================================================

   double h1_fast =
      0.0;


   double h1_mid =
      0.0;


   double h1_slow =
      0.0;


   double h1_atr =
      0.0;


   TradeDirection h1_direction =
      TrendDirectionH1(
         h1_fast,
         h1_mid,
         h1_slow,
         h1_atr,
         h1_separation_atr
      );


   if(
      h1_direction ==
      DIR_NONE
   )
      return false;


   //===============================================================
   // H4
   //===============================================================

   double h4_mid =
      0.0;


   double h4_slow =
      0.0;


   double h4_atr =
      0.0;


   TradeDirection h4_direction =
      TrendDirectionH4(
         h4_mid,
         h4_slow,
         h4_atr,
         h4_slope_atr
      );


   if(
      h4_direction ==
      DIR_NONE
   )
      return false;


   if(
      h1_direction !=
      h4_direction
   )
      return false;


   //===============================================================
   // M15 ADX / DI
   //===============================================================

   if(
      !GetADX(
         TF_SETUP,
         1,
         adx,
         plus_di,
         minus_di
      )
   )
      return false;


   if(
      adx <
      MIN_TREND_ADX
   )
      return false;


   // Slight tolerance rather than requiring massive DI dominance.

   if(
      h1_direction ==
      DIR_LONG
   )
   {
      if(
         plus_di <
         minus_di *
         0.90
      )
         return false;
   }


   if(
      h1_direction ==
      DIR_SHORT
   )
   {
      if(
         minus_di <
         plus_di *
         0.90
      )
         return false;
   }


   direction =
      h1_direction;


   //===============================================================
   // REGIME SCORE
   //===============================================================

   regime_score =
      18;


   if(
      adx >=
      23.0
   )
   {
      regime_score +=
         2;
   }


   if(
      adx >=
      STRONG_TREND_ADX
   )
   {
      regime_score +=
         3;
   }


   if(
      adx >=
      VERY_STRONG_TREND_ADX
   )
   {
      regime_score +=
         2;
   }


   double directional_advantage =
      0.0;


   if(
      direction ==
      DIR_LONG
   )
   {
      directional_advantage =
         plus_di -
         minus_di;
   }
   else
   {
      directional_advantage =
         minus_di -
         plus_di;
   }


   if(
      directional_advantage >=
      5.0
   )
   {
      regime_score +=
         2;
   }


   if(
      directional_advantage >=
      10.0
   )
   {
      regime_score +=
         1;
   }


   regime_score =
      MathMin(
         regime_score,
         28
      );


   //===============================================================
   // HTF SCORE
   //===============================================================

   htf_score =
      12;


   if(
      h1_separation_atr >=
      STRONG_H1_EMA_SEPARATION_ATR
   )
   {
      htf_score +=
         3;
   }


   if(
      h1_separation_atr >=
      0.40
   )
   {
      htf_score +=
         2;
   }


   if(
      MathAbs(
         h4_slope_atr
      )
      >=
      STRONG_H4_SLOPE_ATR
   )
   {
      htf_score +=
         3;
   }


   htf_score =
      MathMin(
         htf_score,
         20
      );


   //===============================================================
   // STRUCTURE SCORE
   //===============================================================

   if(
      M15StructureAligned(
         direction
      )
   )
   {
      structure_score =
         8;
   }
   else
   {
      structure_score =
         4;
   }


   return true;
}


//==================================================================
// SESSION SCORE
//==================================================================

int SessionScore(
   string session
)
{
   if(
      session ==
      "Asia"
   )
      return ASIA_SCORE_BONUS;


   if(
      session ==
      "London"
   )
      return LONDON_SCORE_BONUS;


   if(
      session ==
      "NewYork"
   )
      return NEWYORK_SCORE_BONUS;


   return 0;
}


//==================================================================
// DIRECTION SCORE
//==================================================================

int DirectionScore(
   TradeDirection direction
)
{
   if(
      direction ==
      DIR_SHORT
   )
      return SELL_QUALITY_BONUS;


   if(
      direction ==
      DIR_LONG
   )
      return BUY_QUALITY_BONUS;


   return 0;
}


//==================================================================
// EXPANSION SCORE V2.3
//
// Weak expansions no longer receive almost the same credit as
// genuinely impulsive bars.
//==================================================================

int ExpansionScoreV23(
   double range_multiple,
   double body_pct
)
{
   int score =
      6;


   //===============================================================
   // RANGE QUALITY
   //===============================================================

   if(
      range_multiple >=
      QUALITY_EXPANSION_MULT
   )
      score +=
         4;


   if(
      range_multiple >=
      STRONG_EXPANSION_MULT
   )
      score +=
         4;


   if(
      range_multiple >=
      ELITE_EXPANSION_MULT
   )
      score +=
         4;


   if(
      range_multiple >=
      2.75
   )
      score +=
         2;


   //===============================================================
   // BODY QUALITY
   //===============================================================

   if(
      body_pct >=
      QUALITY_BODY_PCT
   )
      score +=
         4;


   if(
      body_pct >=
      STRONG_BODY_PCT
   )
      score +=
         2;


   if(
      body_pct >=
      ELITE_BODY_PCT
   )
      score +=
         2;


   return MathMin(
      score,
      28
   );
}


//==================================================================
// RETRACE SCORE V2.3
//==================================================================

int RetraceScoreV23(
   double retrace_pct,
   bool fvg_present,
   bool inside_fvg
)
{
   int score =
      4;


   if(
      retrace_pct >=
      RETRACE_ACCEPTABLE_MIN
      &&
      retrace_pct <=
      RETRACE_ACCEPTABLE_MAX
   )
   {
      score +=
         3;
   }


   if(
      retrace_pct >=
      RETRACE_IDEAL_MIN
      &&
      retrace_pct <=
      RETRACE_IDEAL_MAX
   )
   {
      score +=
         4;
   }


   if(
      retrace_pct >=
      RETRACE_ELITE_MIN
      &&
      retrace_pct <=
      RETRACE_ELITE_MAX
   )
   {
      score +=
         2;
   }


   // FVG is intentionally only a small confluence.
   // V2.2 did NOT justify making FVG mandatory.

   if(
      fvg_present
   )
   {
      score +=
         1;
   }


   if(
      inside_fvg
   )
   {
      score +=
         2;
   }


   return MathMin(
      score,
      16
   );
}


//==================================================================
// RAW QUALITY CLASS
//
// This evaluates the actual impulse quality BEFORE total score.
//==================================================================

SignalQuality ClassifyRawQuality(
   double expansion_multiple,
   double body_pct
)
{
   //===============================================================
   // ELITE
   //===============================================================

   if(
      expansion_multiple >=
      ELITE_EXPANSION_MULT
      &&
      body_pct >=
      STRONG_BODY_PCT
   )
   {
      return QUALITY_ELITE;
   }


   if(
      expansion_multiple >=
      STRONG_EXPANSION_MULT
      &&
      body_pct >=
      ELITE_BODY_PCT
   )
   {
      return QUALITY_ELITE;
   }


   //===============================================================
   // STRONG
   //===============================================================

   if(
      expansion_multiple >=
      STRONG_EXPANSION_MULT
      &&
      body_pct >=
      QUALITY_BODY_PCT
   )
   {
      return QUALITY_STRONG;
   }


   if(
      expansion_multiple >=
      QUALITY_EXPANSION_MULT
      &&
      body_pct >=
      STRONG_BODY_PCT
   )
   {
      return QUALITY_STRONG;
   }


   //===============================================================
   // STANDARD
   //===============================================================

   if(
      expansion_multiple >=
      QUALITY_EXPANSION_MULT
      &&
      body_pct >=
      QUALITY_BODY_PCT
   )
   {
      return QUALITY_STANDARD;
   }


   // Weak expansion remains eligible ONLY through the exceptional
   // score override later.

   return QUALITY_REJECT;
}


//==================================================================
// QUALITY SCORE BONUS
//==================================================================

int QualityScore(
   SignalQuality quality
)
{
   if(
      quality ==
      QUALITY_ELITE
   )
      return 8;


   if(
      quality ==
      QUALITY_STRONG
   )
      return 5;


   if(
      quality ==
      QUALITY_STANDARD
   )
      return 2;


   return 0;
}


//==================================================================
// REQUIRED SCORE
//==================================================================

int RequiredScoreForQuality(
   SignalQuality quality
)
{
   if(
      quality ==
      QUALITY_ELITE
   )
      return SCORE_ELITE_MIN;


   if(
      quality ==
      QUALITY_STRONG
   )
      return SCORE_STRONG_MIN;


   if(
      quality ==
      QUALITY_STANDARD
   )
      return SCORE_STANDARD_MIN;


   return SCORE_EXCEPTIONAL;
}


//==================================================================
// FVG DETECTION V2.3
//
// Uses the classical three-candle imbalance:
//
// bullish:
// candle 1 low > candle 3 high
//
// bearish:
// candle 1 high < candle 3 low
//
// With series arrays:
// rates[0] = expansion
// rates[2] = candle two bars before expansion
//==================================================================

bool DetectExpansionFVG(
   TradeDirection direction,
   MqlRates &rates[],
   double &fvg_low,
   double &fvg_high
)
{
   fvg_low =
      0.0;


   fvg_high =
      0.0;


   if(
      ArraySize(
         rates
      )
      < 3
   )
      return false;


   if(
      direction ==
      DIR_LONG
   )
   {
      if(
         rates[0].low >
         rates[2].high
      )
      {
         fvg_low =
            rates[2].high;


         fvg_high =
            rates[0].low;


         return true;
      }
   }


   if(
      direction ==
      DIR_SHORT
   )
   {
      if(
         rates[0].high <
         rates[2].low
      )
      {
         fvg_low =
            rates[0].high;


         fvg_high =
            rates[2].low;


         return true;
      }
   }


   return false;
}


//==================================================================
// ARM EXPANSION
//==================================================================

bool DetectAndArmExpansion()
{
   if(
      !SessionAllowed()
   )
      return false;


   if(
      !FridayAllowed()
   )
      return false;


   //===============================================================
   // REGIME
   //===============================================================

   TradeDirection direction =
      DIR_NONE;


   double adx =
      0.0;


   double plus_di =
      0.0;


   double minus_di =
      0.0;


   double h1_separation_atr =
      0.0;


   double h4_slope_atr =
      0.0;


   int regime_score =
      0;


   int htf_score =
      0;


   int structure_score =
      0;


   if(
      !StrongTrendRegime(
         direction,
         adx,
         plus_di,
         minus_di,
         h1_separation_atr,
         h4_slope_atr,
         regime_score,
         htf_score,
         structure_score
      )
   )
      return false;


   //===============================================================
   // M5 DATA
   //===============================================================

   MqlRates rates[];


   int required =
      EXPANSION_LOOKBACK +
      4;


   if(
      !GetRatesData(
         TF_ENTRY,
         1,
         required,
         rates
      )
   )
      return false;


   MqlRates expansion =
      rates[0];


   double expansion_range =
      CandleRange(
         expansion
      );


   if(
      expansion_range <= 0.0
   )
      return false;


   double expansion_body =
      CandleBody(
         expansion
      );


   double body_pct =
      expansion_body /
      expansion_range;


   if(
      body_pct <
      DETECT_MIN_BODY_PCT
   )
      return false;


   //===============================================================
   // AVERAGE RANGE
   //===============================================================

   double average_range =
      0.0;


   for(
      int i = 1;
      i <= EXPANSION_LOOKBACK;
      i++
   )
   {
      average_range +=
         CandleRange(
            rates[i]
         );
   }


   average_range /=
      EXPANSION_LOOKBACK;


   if(
      average_range <= 0.0
   )
      return false;


   double range_multiple =
      expansion_range /
      average_range;


   if(
      range_multiple <
      DETECT_MIN_EXPANSION_MULT
   )
      return false;


   //===============================================================
   // BREAKOUT REFERENCE
   //===============================================================

   double prior_high =
      HighestHigh(
         rates,
         1,
         EXPANSION_LOOKBACK
      );


   double prior_low =
      LowestLow(
         rates,
         1,
         EXPANSION_LOOKBACK
      );


   //===============================================================
   // DIRECTIONAL BREAKOUT
   //===============================================================

   if(
      direction ==
      DIR_LONG
   )
   {
      if(
         !Bullish(
            expansion
         )
      )
         return false;


      if(
         expansion.close <=
         prior_high
      )
         return false;
   }


   if(
      direction ==
      DIR_SHORT
   )
   {
      if(
         !Bearish(
            expansion
         )
      )
         return false;


      if(
         expansion.close >=
         prior_low
      )
         return false;
   }


   //===============================================================
   // ATR
   //===============================================================

   double atr =
      0.0;


   if(
      !GetATR(
         TF_ENTRY,
         1,
         atr
      )
   )
      return false;


   if(
      atr <= 0.0
   )
      return false;


   //===============================================================
   // FVG
   //===============================================================

   double fvg_low =
      0.0;


   double fvg_high =
      0.0;


   bool fvg_present =
      DetectExpansionFVG(
         direction,
         rates,
         fvg_low,
         fvg_high
      );


   //===============================================================
   // CREATE SETUP
   //===============================================================

   ResetSetup();


   setup.active =
      true;


   setup.direction =
      direction;


   setup.expansion_time =
      expansion.time;


   setup.armed_time =
      TimeCurrent();


   setup.expiry_time =
      setup.armed_time +
      RETRACE_MAX_BARS *
      PeriodSeconds(
         TF_ENTRY
      );


   setup.bars_alive =
      0;


   setup.expansion_high =
      expansion.high;


   setup.expansion_low =
      expansion.low;


   setup.expansion_open =
      expansion.open;


   setup.expansion_close =
      expansion.close;


   setup.expansion_range =
      expansion_range;


   setup.body_pct =
      body_pct;


   setup.average_range =
      average_range;


   setup.range_multiple =
      range_multiple;


   setup.atr =
      atr;


   setup.adx =
      adx;


   setup.plus_di =
      plus_di;


   setup.minus_di =
      minus_di;


   setup.prior_high =
      prior_high;


   setup.prior_low =
      prior_low;


   setup.fvg_present =
      fvg_present;


   setup.fvg_low =
      fvg_low;


   setup.fvg_high =
      fvg_high;


   setup.base_regime_score =
      regime_score;


   setup.base_htf_score =
      htf_score;


   setup.base_expansion_score =
      ExpansionScoreV23(
         range_multiple,
         body_pct
      );


   setup.base_structure_score =
      structure_score;


   setup.session =
      CurrentSession();


   setup.base_session_score =
      SessionScore(
         setup.session
      );


   setup.base_direction_score =
      DirectionScore(
         direction
      );


   //===============================================================
   // INVALIDATION
   //===============================================================

   if(
      direction ==
      DIR_LONG
   )
   {
      setup.invalidation_price =
         NormalizePrice(
            expansion.low -
            atr *
            SETUP_INVALIDATION_ATR
         );
   }
   else
   {
      setup.invalidation_price =
         NormalizePrice(
            expansion.high +
            atr *
            SETUP_INVALIDATION_ATR
         );
   }


   return true;
}


//==================================================================
// SETUP AGE
//==================================================================

int SetupAgeBars()
{
   if(
      !setup.active
   )
      return 0;


   int seconds =
      PeriodSeconds(
         TF_ENTRY
      );


   if(
      seconds <= 0
   )
      return 0;


   int age =
      (int)(
         (
            TimeCurrent() -
            setup.armed_time
         )
         /
         seconds
      );


   if(
      age < 0
   )
      age =
         0;


   return age;
}


//==================================================================
// SETUP EXPIRED
//==================================================================

bool SetupExpired()
{
   if(
      !setup.active
   )
      return true;


   if(
      TimeCurrent() >
      setup.expiry_time
   )
      return true;


   if(
      SetupAgeBars() >=
      RETRACE_MAX_BARS
   )
      return true;


   return false;
}


//==================================================================
// PRICE INVALIDATION
//==================================================================

bool SetupPriceInvalidated()
{
   if(
      !setup.active
   )
      return true;


   MqlTick tick;


   if(
      !GetCurrentTick(
         tick
      )
   )
      return false;


   if(
      setup.direction ==
      DIR_LONG
   )
   {
      if(
         tick.bid <=
         setup.invalidation_price
      )
         return true;
   }


   if(
      setup.direction ==
      DIR_SHORT
   )
   {
      if(
         tick.ask >=
         setup.invalidation_price
      )
         return true;
   }


   return false;
}


//==================================================================
// CURRENT RETRACE
//==================================================================

double CurrentRetracePct(
   TradeDirection direction,
   double price
)
{
   if(
      setup.expansion_range <= 0.0
   )
      return -1.0;


   if(
      direction ==
      DIR_LONG
   )
   {
      return (
         setup.expansion_high -
         price
      )
      /
      setup.expansion_range;
   }


   if(
      direction ==
      DIR_SHORT
   )
   {
      return (
         price -
         setup.expansion_low
      )
      /
      setup.expansion_range;
   }


   return -1.0;
}


//==================================================================
// PRICE INSIDE FVG
//==================================================================

bool PriceInsideFVG(
   double price
)
{
   if(
      !setup.fvg_present
   )
      return false;


   if(
      setup.fvg_low <= 0.0 ||
      setup.fvg_high <= 0.0
   )
      return false;


   double low =
      MathMin(
         setup.fvg_low,
         setup.fvg_high
      );


   double high =
      MathMax(
         setup.fvg_low,
         setup.fvg_high
      );


   return (
      price >= low
      &&
      price <= high
   );
}


//==================================================================
// CURRENT REGIME VALIDATION
//==================================================================

bool SetupRegimeStillValid(
   double &adx,
   double &plus_di,
   double &minus_di,

   int &regime_score,
   int &htf_score,
   int &structure_score
)
{
   TradeDirection direction =
      DIR_NONE;


   double h1_separation =
      0.0;


   double h4_slope =
      0.0;


   if(
      !StrongTrendRegime(
         direction,
         adx,
         plus_di,
         minus_di,
         h1_separation,
         h4_slope,
         regime_score,
         htf_score,
         structure_score
      )
   )
      return false;


   if(
      direction !=
      setup.direction
   )
      return false;


   return true;
}


//==================================================================
// QUALITY ROUTER V2.3
//
// Returns TRUE only when signal quality is acceptable.
//
// IMPORTANT:
// Weak raw expansion is not automatically rejected if the complete
// context reaches SCORE_EXCEPTIONAL.
//
// Delayed setups receive additional protection.
//
// London remains active, but mediocre London signals require more
// confirmation.
//==================================================================

bool QualityRouter(
   TradeSignal &signal
)
{
   SignalQuality raw_quality =
      ClassifyRawQuality(
         signal.expansion_multiple,
         signal.expansion_body_pct
      );


   signal.quality =
      raw_quality;


   signal.score_quality =
      QualityScore(
         raw_quality
      );


   signal.score +=
      signal.score_quality;


   signal.score =
      MathMin(
         signal.score,
         100
      );


   int required_score =
      RequiredScoreForQuality(
         raw_quality
      );


   //===============================================================
   // ABSOLUTE FLOOR
   //===============================================================

   required_score =
      MathMax(
         required_score,
         SCORE_ABSOLUTE_MIN
      );


   //===============================================================
   // LONDON
   //===============================================================

   if(
      signal.session ==
      "London"
   )
   {
      required_score =
         MathMax(
            required_score,
            LONDON_MIN_SCORE
         );


      if(
         signal.expansion_multiple <
         LONDON_MIN_EXPANSION
         &&
         signal.score <
         SCORE_EXCEPTIONAL
      )
      {
         signal.required_score =
            required_score;


         signal.reason =
            "London expansion too weak";


         return false;
      }
   }


   //===============================================================
   // DELAYED SETUP
   //===============================================================

   if(
      signal.setup_age_bars >=
      DELAYED_SETUP_FROM_BAR
   )
   {
      required_score =
         MathMax(
            required_score,
            DELAYED_SETUP_MIN_SCORE
         );


      if(
         signal.expansion_multiple <
         DELAYED_SETUP_MIN_EXPANSION
      )
      {
         signal.required_score =
            required_score;


         signal.reason =
            "Delayed setup expansion too weak";


         return false;
      }


      if(
         signal.expansion_body_pct <
         DELAYED_SETUP_MIN_BODY
      )
      {
         signal.required_score =
            required_score;


         signal.reason =
            "Delayed setup body too weak";


         return false;
      }
   }


   //===============================================================
   // WEAK RAW QUALITY EXCEPTION
   //===============================================================

   if(
      raw_quality ==
      QUALITY_REJECT
   )
   {
      required_score =
         SCORE_EXCEPTIONAL;


      if(
         signal.score <
         required_score
      )
      {
         signal.required_score =
            required_score;


         signal.reason =
            "Weak expansion without exceptional score";


         return false;
      }


      // It passed through exceptional context.
      // Mark as STANDARD for research rather than REJECT.

      signal.quality =
         QUALITY_STANDARD;
   }


   signal.required_score =
      required_score;


   if(
      signal.score <
      required_score
   )
   {
      signal.reason =
         "Quality score below adaptive threshold";


      return false;
   }


   return true;
}


//==================================================================
// BUILD RETRACE SIGNAL
//==================================================================

TradeSignal BuildRetraceSignal()
{
   TradeSignal signal =
      EmptySignal();


   if(
      !setup.active
   )
   {
      signal.reason =
         "No active setup";


      return signal;
   }


   if(
      SetupExpired()
   )
   {
      signal.reason =
         "Setup expired";


      return signal;
   }


   if(
      SetupPriceInvalidated()
   )
   {
      signal.reason =
         "Setup invalidated";


      return signal;
   }


   //===============================================================
   // CURRENT PRICE
   //===============================================================

   MqlTick tick;


   if(
      !GetCurrentTick(
         tick
      )
   )
   {
      signal.reason =
         "No tick";


      return signal;
   }


   double entry =
      setup.direction ==
      DIR_LONG
      ?
      tick.ask
      :
      tick.bid;


   //===============================================================
   // RETRACE
   //===============================================================

   double retrace_pct =
      CurrentRetracePct(
         setup.direction,
         entry
      );


   if(
      retrace_pct <
      RETRACE_MIN_PCT
   )
   {
      signal.reason =
         "Waiting for retrace";


      return signal;
   }


   if(
      retrace_pct >
      RETRACE_MAX_PCT
   )
   {
      signal.reason =
         "Retrace too deep";


      return signal;
   }


   //===============================================================
   // CURRENT REGIME
   //===============================================================

   double current_adx =
      0.0;


   double current_plus_di =
      0.0;


   double current_minus_di =
      0.0;


   int current_regime_score =
      0;


   int current_htf_score =
      0;


   int current_structure_score =
      0;


   if(
      !SetupRegimeStillValid(
         current_adx,
         current_plus_di,
         current_minus_di,
         current_regime_score,
         current_htf_score,
         current_structure_score
      )
   )
   {
      signal.reason =
         "Regime no longer valid";


      return signal;
   }


   //===============================================================
   // FVG
   //===============================================================

   bool inside_fvg =
      PriceInsideFVG(
         entry
      );


   //===============================================================
   // SCORE COMPONENTS
   //===============================================================

   int expansion_score =
      ExpansionScoreV23(
         setup.range_multiple,
         setup.body_pct
      );


   int retrace_score =
      RetraceScoreV23(
         retrace_pct,
         setup.fvg_present,
         inside_fvg
      );


   string current_session =
      CurrentSession();


   int session_score =
      SessionScore(
         current_session
      );


   int direction_score =
      DirectionScore(
         setup.direction
      );


   int base_score =
      current_regime_score +
      current_htf_score +
      expansion_score +
      current_structure_score +
      retrace_score +
      session_score +
      direction_score;


   base_score =
      MathMin(
         base_score,
         100
      );


   //===============================================================
   // POPULATE SIGNAL BEFORE QUALITY ROUTER
   //===============================================================

   signal.direction =
      setup.direction;


   signal.entry =
      entry;


   signal.atr =
      setup.atr;


   signal.adx =
      current_adx;


   signal.plus_di =
      current_plus_di;


   signal.minus_di =
      current_minus_di;


   signal.expansion_time =
      setup.expansion_time;


   signal.expansion_high =
      setup.expansion_high;


   signal.expansion_low =
      setup.expansion_low;


   signal.expansion_open =
      setup.expansion_open;


   signal.expansion_close =
      setup.expansion_close;


   signal.expansion_range =
      setup.expansion_range;


   signal.expansion_body_pct =
      setup.body_pct;


   signal.expansion_multiple =
      setup.range_multiple;


   signal.retrace_pct =
      retrace_pct;


   signal.setup_age_bars =
      SetupAgeBars();


   signal.fvg_present =
      setup.fvg_present;


   signal.inside_fvg =
      inside_fvg;


   signal.fvg_low =
      setup.fvg_low;


   signal.fvg_high =
      setup.fvg_high;


   signal.score_regime =
      current_regime_score;


   signal.score_htf =
      current_htf_score;


   signal.score_expansion =
      expansion_score;


   signal.score_structure =
      current_structure_score;


   signal.score_retrace =
      retrace_score;


   signal.score_session =
      session_score;


   signal.score_direction =
      direction_score;


   signal.score_quality =
      0;


   signal.score =
      base_score;


   signal.session =
      current_session;


   signal.reason =
      "V2.3 quality candidate";


   //===============================================================
   // ADAPTIVE QUALITY ROUTER
   //===============================================================

   if(
      !QualityRouter(
         signal
      )
   )
   {
      signal.valid =
         false;


      return signal;
   }


   //===============================================================
   // STOP LOSS
   //
   // Keep the proven structural stop from V2.2.
   // We are improving entries first, not simultaneously changing
   // every dimension of the strategy.
   //===============================================================

   double sl =
      0.0;


   if(
      setup.direction ==
      DIR_LONG
   )
   {
      sl =
         NormalizePrice(
            setup.expansion_low -
            setup.atr *
            0.10
         );
   }
   else
   {
      sl =
         NormalizePrice(
            setup.expansion_high +
            setup.atr *
            0.10
         );
   }


   double risk_distance =
      MathAbs(
         entry -
         sl
      );


   if(
      risk_distance <= 0.0
   )
   {
      signal.reason =
         "Invalid risk distance";


      signal.valid =
         false;


      return signal;
   }


   //===============================================================
   // 5R TARGET
   //===============================================================

   double tp =
      0.0;


   if(
      setup.direction ==
      DIR_LONG
   )
   {
      tp =
         NormalizePrice(
            entry +
            risk_distance *
            TP_R
         );
   }
   else
   {
      tp =
         NormalizePrice(
            entry -
            risk_distance *
            TP_R
         );
   }


   entry =
      NormalizePrice(
         entry
      );


   if(
      !StopsValid(
         setup.direction,
         entry,
         sl,
         tp
      )
   )
   {
      signal.reason =
         "Broker stop validation";


      signal.valid =
         false;


      return signal;
   }


   //===============================================================
   // FINAL SIGNAL
   //===============================================================

   signal.entry =
      entry;


   signal.sl =
      sl;


   signal.tp =
      tp;


   signal.risk_distance =
      risk_distance;


   signal.valid =
      true;


   signal.reason =
      "V2.3 adaptive quality pass";


   return signal;
}


//==================================================================
// MARGIN CHECK
//==================================================================

bool MarginAllowed(
   TradeDirection direction,
   double volume,
   double entry
)
{
   ENUM_ORDER_TYPE order_type =
      direction ==
      DIR_LONG
      ?
      ORDER_TYPE_BUY
      :
      ORDER_TYPE_SELL;


   double required_margin =
      0.0;


   if(
      !OrderCalcMargin(
         order_type,
         SYMBOL_NAME,
         volume,
         entry,
         required_margin
      )
   )
      return false;


   double free_margin =
      AccountInfoDouble(
         ACCOUNT_MARGIN_FREE
      );


   return (
      required_margin <
      free_margin *
      0.90
   );
}


//==================================================================
// EXECUTE SIGNAL
//==================================================================

bool ExecuteSignal(
   TradeSignal &signal
)
{
   if(
      !signal.valid
   )
      return false;


   if(
      !GlobalEntryAllowed()
   )
      return false;


   MqlTick tick;


   if(
      !GetCurrentTick(
         tick
      )
   )
      return false;


   //===============================================================
   // ACTUAL EXECUTION PRICE
   //===============================================================

   double actual_entry =
      signal.direction ==
      DIR_LONG
      ?
      tick.ask
      :
      tick.bid;


   double actual_sl =
      signal.sl;


   double actual_risk =
      MathAbs(
         actual_entry -
         actual_sl
      );


   if(
      actual_risk <= 0.0
   )
      return false;


   //===============================================================
   // RECALCULATE 5R FROM ACTUAL ENTRY
   //===============================================================

   double actual_tp =
      0.0;


   if(
      signal.direction ==
      DIR_LONG
   )
   {
      actual_tp =
         NormalizePrice(
            actual_entry +
            actual_risk *
            TP_R
         );
   }
   else
   {
      actual_tp =
         NormalizePrice(
            actual_entry -
            actual_risk *
            TP_R
         );
   }


   actual_entry =
      NormalizePrice(
         actual_entry
      );


   actual_sl =
      NormalizePrice(
         actual_sl
      );


   if(
      !StopsValid(
         signal.direction,
         actual_entry,
         actual_sl,
         actual_tp
      )
   )
      return false;


   //===============================================================
   // POSITION SIZE
   //===============================================================

   double risk_money =
      0.0;


   double volume =
      CalculateVolume(
         signal.direction,
         actual_entry,
         actual_sl,
         risk_money
      );


   if(
      volume <= 0.0
   )
      return false;


   if(
      !MarginAllowed(
         signal.direction,
         volume,
         actual_entry
      )
   )
      return false;


   //===============================================================
   // STORE ACTUAL VALUES
   //===============================================================

   signal.entry =
      actual_entry;


   signal.sl =
      actual_sl;


   signal.tp =
      actual_tp;


   signal.risk_distance =
      actual_risk;


   //===============================================================
   // PENDING METADATA
   //===============================================================

   pending_entry_signal =
      signal;


   pending_entry_signal_valid =
      true;


   //===============================================================
   // ORDER
   //===============================================================

   trade.SetExpertMagicNumber(
      MAGIC
   );


   trade.SetDeviationInPoints(
      30
   );


   ResetLastError();


   bool sent =
      false;


   string order_comment =
      "XV23_" +
      QualityName(
         signal.quality
      );


   if(
      signal.direction ==
      DIR_LONG
   )
   {
      sent =
         trade.Buy(
            volume,
            SYMBOL_NAME,
            0.0,
            actual_sl,
            actual_tp,
            order_comment
         );
   }
   else
   {
      sent =
         trade.Sell(
            volume,
            SYMBOL_NAME,
            0.0,
            actual_sl,
            actual_tp,
            order_comment
         );
   }


   ulong retcode =
      trade.ResultRetcode();


   bool accepted =
      (
         retcode ==
         TRADE_RETCODE_DONE
         ||
         retcode ==
         TRADE_RETCODE_DONE_PARTIAL
         ||
         retcode ==
         TRADE_RETCODE_PLACED
      );


   if(
      !sent ||
      !accepted
   )
   {
      ResetPendingSignal();


      return false;
   }


   RegisterEntryTime();


   ResetSetup();


   return true;
}


//==================================================================
// PROCESS ACTIVE SETUP
//==================================================================

void ProcessActiveSetup()
{
   if(
      !setup.active
   )
      return;


   if(
      SetupExpired()
   )
   {
      ResetSetup();


      return;
   }


   if(
      SetupPriceInvalidated()
   )
   {
      ResetSetup();


      return;
   }


   if(
      !GlobalEntryAllowed()
   )
      return;


   TradeSignal signal =
      BuildRetraceSignal();


   if(
      !signal.valid
   )
   {
      // These invalidate the setup itself.

      if(
         signal.reason ==
         "Regime no longer valid"
         ||
         signal.reason ==
         "Retrace too deep"
         ||
         signal.reason ==
         "Setup invalidated"
      )
      {
         ResetSetup();
      }


      // Quality rejection does NOT instantly delete the setup.
      // Price may move deeper into a better retracement zone while
      // the setup remains valid.

      return;
   }


   ExecuteSignal(
      signal
   );
}


//==================================================================
// PROCESS NEW M5 BAR
//==================================================================

void ProcessNewM5Bar()
{
   if(
      setup.active
   )
   {
      setup.bars_alive =
         SetupAgeBars();


      if(
         SetupExpired()
      )
      {
         ResetSetup();
      }
   }


   if(
      BotPositionCount()
      >=
      MAX_POSITIONS
   )
      return;


   // V2.3:
   // If no setup is active, arm the latest valid expansion.
   //
   // We intentionally do NOT continuously replace a still-valid
   // impulse with every newer candle.

   if(
      !setup.active
   )
   {
      DetectAndArmExpansion();
   }
}


//==================================================================
// ENTRY ENGINE
//==================================================================

void RunEntryEngine()
{
   if(
      IsNewM5Bar()
   )
   {
      ProcessNewM5Bar();
   }


   ProcessActiveSetup();
}


//==================================================================
// COPY SIGNAL -> POSITION STATE
//==================================================================

void ApplySignalToState(
   PositionState &state,
   TradeSignal &signal
)
{
   state.direction =
      signal.direction;


   state.quality =
      signal.quality;


   state.session =
      signal.session;


   state.score =
      signal.score;


   state.required_score =
      signal.required_score;


   state.score_regime =
      signal.score_regime;


   state.score_htf =
      signal.score_htf;


   state.score_expansion =
      signal.score_expansion;


   state.score_structure =
      signal.score_structure;


   state.score_retrace =
      signal.score_retrace;


   state.score_session =
      signal.score_session;


   state.score_direction =
      signal.score_direction;


   state.score_quality =
      signal.score_quality;


   state.signal_atr =
      signal.atr;


   state.signal_adx =
      signal.adx;


   state.signal_plus_di =
      signal.plus_di;


   state.signal_minus_di =
      signal.minus_di;


   state.expansion_time =
      signal.expansion_time;


   state.expansion_range =
      signal.expansion_range;


   state.expansion_body_pct =
      signal.expansion_body_pct;


   state.expansion_multiple =
      signal.expansion_multiple;


   state.retrace_pct =
      signal.retrace_pct;


   state.setup_age_bars =
      signal.setup_age_bars;


   state.fvg_present =
      signal.fvg_present;


   state.inside_fvg =
      signal.inside_fvg;


   state.fvg_low =
      signal.fvg_low;


   state.fvg_high =
      signal.fvg_high;


   state.entry_reason =
      signal.reason;
}


//==================================================================
// END PART 2
//==================================================================//==================================================================
// PART 3A
// POSITION STATE + RESEARCH LOGGING + MANAGEMENT
//==================================================================


//==================================================================
// STATE LOOKUP
//==================================================================

int FindStateByPositionId(
   ulong position_id
)
{
   for(
      int i = 0;
      i < ArraySize(states);
      i++
   )
   {
      if(
         states[i].position_id ==
         position_id
      )
         return i;
   }


   return -1;
}


//==================================================================
// FIND BOT POSITION
//==================================================================

bool FindBotPosition(
   ulong &ticket,
   ulong &position_id
)
{
   ticket =
      0;


   position_id =
      0;


   for(
      int i =
      PositionsTotal() - 1;
      i >= 0;
      i--
   )
   {
      ulong current_ticket =
         PositionGetTicket(
            i
         );


      if(
         current_ticket == 0
      )
         continue;


      if(
         !PositionSelectByTicket(
            current_ticket
         )
      )
         continue;


      if(
         PositionGetString(
            POSITION_SYMBOL
         )
         !=
         SYMBOL_NAME
      )
         continue;


      if(
         PositionGetInteger(
            POSITION_MAGIC
         )
         !=
         (long)MAGIC
      )
         continue;


      ticket =
         current_ticket;


      position_id =
         (ulong)
         PositionGetInteger(
            POSITION_IDENTIFIER
         );


      return true;
   }


   return false;
}


//==================================================================
// POSITION EXISTS
//==================================================================

bool PositionStillExists(
   ulong position_id
)
{
   for(
      int i =
      PositionsTotal() - 1;
      i >= 0;
      i--
   )
   {
      ulong ticket =
         PositionGetTicket(
            i
         );


      if(
         ticket == 0
      )
         continue;


      if(
         !PositionSelectByTicket(
            ticket
         )
      )
         continue;


      if(
         PositionGetString(
            POSITION_SYMBOL
         )
         !=
         SYMBOL_NAME
      )
         continue;


      if(
         PositionGetInteger(
            POSITION_MAGIC
         )
         !=
         (long)MAGIC
      )
         continue;


      ulong current_id =
         (ulong)
         PositionGetInteger(
            POSITION_IDENTIFIER
         );


      if(
         current_id ==
         position_id
      )
         return true;
   }


   return false;
}


//==================================================================
// REMOVE STATE
//==================================================================

void RemoveState(
   int index
)
{
   int total =
      ArraySize(
         states
      );


   if(
      index < 0 ||
      index >= total
   )
      return;


   for(
      int i = index;
      i < total - 1;
      i++
   )
   {
      states[i] =
         states[i + 1];
   }


   ArrayResize(
      states,
      total - 1
   );
}


//==================================================================
// CURRENT R
//==================================================================

double CurrentR(
   PositionState &state,
   double price
)
{
   if(
      state.risk_distance <= 0.0
   )
      return 0.0;


   if(
      state.direction ==
      DIR_LONG
   )
   {
      return (
         price -
         state.entry
      )
      /
      state.risk_distance;
   }


   return (
      state.entry -
      price
   )
   /
   state.risk_distance;
}


//==================================================================
// PRICE AT R
//==================================================================

double PriceAtR(
   PositionState &state,
   double r
)
{
   if(
      state.direction ==
      DIR_LONG
   )
   {
      return NormalizePrice(
         state.entry +
         state.risk_distance *
         r
      );
   }


   return NormalizePrice(
      state.entry -
      state.risk_distance *
      r
   );
}


//==================================================================
// OPEN LOG FILES
//==================================================================

void OpenLogFiles()
{
   trade_file =
      FileOpen(
         TRADE_CSV,
         FILE_WRITE |
         FILE_CSV |
         FILE_ANSI,
         ';'
      );


   if(
      trade_file !=
      INVALID_HANDLE
   )
   {
      FileWrite(
         trade_file,

         "time",
         "event",

         "position_id",
         "ticket",

         "side",
         "quality",

         "volume",

         "entry",
         "initial_sl",
         "initial_tp",

         "risk_distance",
         "risk_money",

         "profit",

         "max_r",
         "min_r",

         "session",

         "score",
         "required_score",

         "score_regime",
         "score_htf",
         "score_expansion",
         "score_structure",
         "score_retrace",
         "score_session",
         "score_direction",
         "score_quality",

         "atr",
         "adx",
         "plus_di",
         "minus_di",

         "expansion_range",
         "expansion_body_pct",
         "expansion_multiple",

         "retrace_pct",

         "setup_age_bars",

         "fvg_present",
         "inside_fvg",
         "fvg_low",
         "fvg_high",

         "expansion_time",

         "lock_done",

         "entry_reason",

         "comment"
      );


      FileFlush(
         trade_file
      );
   }


   diag_file =
      FileOpen(
         DIAG_CSV,
         FILE_WRITE |
         FILE_CSV |
         FILE_ANSI,
         ';'
      );


   if(
      diag_file !=
      INVALID_HANDLE
   )
   {
      FileWrite(
         diag_file,

         "time",
         "category",

         "position_id",

         "value1",
         "value2",
         "value3",

         "retcode",

         "message"
      );


      FileFlush(
         diag_file
      );
   }
}


//==================================================================
// CLOSE LOG FILES
//==================================================================

void CloseLogFiles()
{
   if(
      trade_file !=
      INVALID_HANDLE
   )
   {
      FileClose(
         trade_file
      );


      trade_file =
         INVALID_HANDLE;
   }


   if(
      diag_file !=
      INVALID_HANDLE
   )
   {
      FileClose(
         diag_file
      );


      diag_file =
         INVALID_HANDLE;
   }
}


//==================================================================
// DIAGNOSTIC LOG
//==================================================================

void LogDiag(
   string category,
   ulong position_id,
   double value1,
   double value2,
   double value3,
   ulong retcode,
   string message
)
{
   if(
      diag_file ==
      INVALID_HANDLE
   )
      return;


   FileWrite(
      diag_file,

      TimeToString(
         TimeCurrent(),
         TIME_DATE |
         TIME_SECONDS
      ),

      category,

      position_id,

      value1,
      value2,
      value3,

      retcode,

      message
   );


   FileFlush(
      diag_file
   );
}


//==================================================================
// TRADE LOG
//==================================================================

void LogTrade(
   string event_name,
   PositionState &state,
   double profit,
   string comment
)
{
   if(
      trade_file ==
      INVALID_HANDLE
   )
      return;


   FileWrite(
      trade_file,

      TimeToString(
         TimeCurrent(),
         TIME_DATE |
         TIME_SECONDS
      ),

      event_name,

      state.position_id,
      state.ticket,

      state.direction ==
      DIR_LONG
      ?
      "BUY"
      :
      "SELL",

      QualityName(
         state.quality
      ),

      state.volume,

      state.entry,
      state.initial_sl,
      state.initial_tp,

      state.risk_distance,
      state.initial_risk_money,

      profit,

      state.max_r,
      state.min_r,

      state.session,

      state.score,
      state.required_score,

      state.score_regime,
      state.score_htf,
      state.score_expansion,
      state.score_structure,
      state.score_retrace,
      state.score_session,
      state.score_direction,
      state.score_quality,

      state.signal_atr,
      state.signal_adx,
      state.signal_plus_di,
      state.signal_minus_di,

      state.expansion_range,
      state.expansion_body_pct,
      state.expansion_multiple,

      state.retrace_pct,

      state.setup_age_bars,

      state.fvg_present
      ?
      1
      :
      0,

      state.inside_fvg
      ?
      1
      :
      0,

      state.fvg_low,
      state.fvg_high,

      state.expansion_time > 0
      ?
      TimeToString(
         state.expansion_time,
         TIME_DATE |
         TIME_MINUTES
      )
      :
      "",

      state.lock_done
      ?
      1
      :
      0,

      state.entry_reason,

      comment
   );


   FileFlush(
      trade_file
   );
}


//==================================================================
// REGISTER LIVE POSITION
//
// The pending signal contains the exact metadata that generated
// the order.
//
// We register as soon as the broker position becomes visible.
//==================================================================

bool RegisterLivePosition()
{
   ulong ticket =
      0;


   ulong position_id =
      0;


   if(
      !FindBotPosition(
         ticket,
         position_id
      )
   )
      return false;


   int existing =
      FindStateByPositionId(
         position_id
      );


   if(
      existing >= 0
   )
      return true;


   if(
      !PositionSelectByTicket(
         ticket
      )
   )
      return false;


   PositionState state;


   ZeroMemory(
      state
   );


   state.ticket =
      ticket;


   state.position_id =
      position_id;


   long position_type =
      PositionGetInteger(
         POSITION_TYPE
      );


   state.direction =
      position_type ==
      POSITION_TYPE_BUY
      ?
      DIR_LONG
      :
      DIR_SHORT;


   state.open_time =
      (datetime)
      PositionGetInteger(
         POSITION_TIME
      );


   state.volume =
      PositionGetDouble(
         POSITION_VOLUME
      );


   state.entry =
      PositionGetDouble(
         POSITION_PRICE_OPEN
      );


   state.initial_sl =
      PositionGetDouble(
         POSITION_SL
      );


   state.initial_tp =
      PositionGetDouble(
         POSITION_TP
      );


   state.risk_distance =
      MathAbs(
         state.entry -
         state.initial_sl
      );


   state.initial_risk_money =
      LossPerLot(
         state.direction,
         state.entry,
         state.initial_sl
      )
      *
      state.volume;


   state.max_r =
      0.0;


   state.min_r =
      0.0;


   state.lock_done =
      false;


   state.lock_attempted =
      false;


   //===============================================================
   // SIGNAL METADATA
   //===============================================================

   if(
      pending_entry_signal_valid
   )
   {
      ApplySignalToState(
         state,
         pending_entry_signal
      );


      ResetPendingSignal();
   }
   else
   {
      // Restart/recovery fallback.
      // Clean Strategy Tester runs should normally never need this.

      state.quality =
         QUALITY_REJECT;


      state.session =
         "Recovered";


      state.score =
         -1;


      state.required_score =
         -1;


      state.score_regime =
         -1;


      state.score_htf =
         -1;


      state.score_expansion =
         -1;


      state.score_structure =
         -1;


      state.score_retrace =
         -1;


      state.score_session =
         -1;


      state.score_direction =
         -1;


      state.score_quality =
         -1;


      state.entry_reason =
         "Recovered position";


      LogDiag(
         "STATE_RECOVERED",
         position_id,
         state.entry,
         state.initial_sl,
         state.initial_tp,
         0,
         "Live position registered without pending signal"
      );
   }


   int size =
      ArraySize(
         states
      );


   ArrayResize(
      states,
      size + 1
   );


   states[size] =
      state;


   LogTrade(
      "OPEN",
      states[size],
      0.0,
      "Position state registered"
   );


   return true;
}


//==================================================================
// SYNC POSITION STATE
//==================================================================

void SyncPositionState()
{
   if(
      BotPositionCount() <= 0
   )
      return;


   RegisterLivePosition();
}


//==================================================================
// UPDATE EXCURSION
//==================================================================

void UpdateExcursion(
   int index
)
{
   if(
      index < 0 ||
      index >= ArraySize(states)
   )
      return;


   if(
      !PositionStillExists(
         states[index].position_id
      )
   )
      return;


   MqlTick tick;


   if(
      !GetCurrentTick(
         tick
      )
   )
      return;


   double price =
      states[index].direction ==
      DIR_LONG
      ?
      tick.bid
      :
      tick.ask;


   double r =
      CurrentR(
         states[index],
         price
      );


   if(
      r >
      states[index].max_r
   )
   {
      states[index].max_r =
         r;
   }


   if(
      r <
      states[index].min_r
   )
   {
      states[index].min_r =
         r;
   }
}


//==================================================================
// UPDATE EXIT EXCURSION
//==================================================================

void UpdateExcursionFromPrice(
   int index,
   double price
)
{
   if(
      index < 0 ||
      index >= ArraySize(states)
   )
      return;


   if(
      price <= 0.0
   )
      return;


   double r =
      CurrentR(
         states[index],
         price
      );


   if(
      r >
      states[index].max_r
   )
   {
      states[index].max_r =
         r;
   }


   if(
      r <
      states[index].min_r
   )
   {
      states[index].min_r =
         r;
   }
}


//==================================================================
// UPDATE ALL EXCURSIONS
//==================================================================

void UpdateAllExcursions()
{
   for(
      int i = 0;
      i < ArraySize(states);
      i++
   )
   {
      if(
         PositionStillExists(
            states[i].position_id
         )
      )
      {
         UpdateExcursion(
            i
         );
      }
   }
}


//==================================================================
// SUCCESSFUL MODIFY RETCODE
//==================================================================

bool ModifyRetcodeSuccessful(
   ulong retcode
)
{
   if(
      retcode ==
      TRADE_RETCODE_DONE
   )
      return true;


   if(
      retcode ==
      TRADE_RETCODE_DONE_PARTIAL
   )
      return true;


   if(
      retcode ==
      TRADE_RETCODE_NO_CHANGES
   )
      return true;


   return false;
}


//==================================================================
// APPLY +3R -> +1R PROFIT LOCK
//==================================================================

bool ApplyProfitLock(
   int index
)
{
   if(
      index < 0 ||
      index >= ArraySize(states)
   )
      return false;


   if(
      states[index].lock_done
   )
      return true;


   ulong ticket =
      states[index].ticket;


   if(
      !PositionSelectByTicket(
         ticket
      )
   )
      return false;


   MqlTick tick;


   if(
      !GetCurrentTick(
         tick
      )
   )
      return false;


   double current_sl =
      PositionGetDouble(
         POSITION_SL
      );


   double current_tp =
      PositionGetDouble(
         POSITION_TP
      );


   double desired_sl =
      PriceAtR(
         states[index],
         LOCK_SL_R
      );


   desired_sl =
      NormalizePrice(
         desired_sl
      );


   double minimum_stop =
      BrokerMinStopDistance();


   //===============================================================
   // LONG
   //===============================================================

   if(
      states[index].direction ==
      DIR_LONG
   )
   {
      if(
         current_sl > 0.0
         &&
         current_sl >=
         desired_sl
      )
      {
         states[index].lock_done =
            true;


         return true;
      }


      if(
         desired_sl >=
         tick.bid
      )
         return false;


      if(
         tick.bid -
         desired_sl <
         minimum_stop
      )
         return false;
   }


   //===============================================================
   // SHORT
   //===============================================================

   if(
      states[index].direction ==
      DIR_SHORT
   )
   {
      if(
         current_sl > 0.0
         &&
         current_sl <=
         desired_sl
      )
      {
         states[index].lock_done =
            true;


         return true;
      }


      if(
         desired_sl <=
         tick.ask
      )
         return false;


      if(
         desired_sl -
         tick.ask <
         minimum_stop
      )
         return false;
   }


   states[index].lock_attempted =
      true;


   trade.SetExpertMagicNumber(
      MAGIC
   );


   ResetLastError();


   bool result =
      trade.PositionModify(
         ticket,
         desired_sl,
         current_tp
      );


   ulong retcode =
      trade.ResultRetcode();


   if(
      result
      &&
      ModifyRetcodeSuccessful(
         retcode
      )
   )
   {
      if(
         PositionSelectByTicket(
            ticket
         )
      )
      {
         double confirmed_sl =
            PositionGetDouble(
               POSITION_SL
            );


         double tolerance =
            TickSize() *
            2.0;


         bool confirmed =
            false;


         if(
            states[index].direction ==
            DIR_LONG
         )
         {
            confirmed =
               confirmed_sl >=
               desired_sl -
               tolerance;
         }
         else
         {
            confirmed =
               confirmed_sl <=
               desired_sl +
               tolerance;
         }


         if(confirmed)
         {
            states[index].lock_done =
               true;


            LogDiag(
               "LOCK_SUCCESS",
               states[index].position_id,
               desired_sl,
               confirmed_sl,
               0.0,
               retcode,
               StringFormat("SL confirmed at +%.2fR", LOCK_SL_R)
            );


            LogTrade(
               "PROFIT_LOCK",
               states[index],
               0.0,
               "Profit lock confirmed"
            );


            return true;
         }
      }
   }


   LogDiag(
      "LOCK_FAIL",
      states[index].position_id,
      desired_sl,
      current_sl,
      0.0,
      retcode,
      trade.ResultRetcodeDescription()
   );


   return false;
}


//==================================================================
// MANAGE POSITION
//==================================================================

void ManagePosition(
   int index
)
{
   if(
      index < 0 ||
      index >= ArraySize(states)
   )
      return;


   if(
      !PositionStillExists(
         states[index].position_id
      )
   )
      return;


   UpdateExcursion(
      index
   );


   //===============================================================
   // ALL FTMO RESEARCH MODES USE A PROFIT LOCK
   //===============================================================


   if(
      states[index].lock_done
   )
      return;


   MqlTick tick;


   if(
      !GetCurrentTick(
         tick
      )
   )
      return;


   double price =
      states[index].direction ==
      DIR_LONG
      ?
      tick.bid
      :
      tick.ask;


   double current_r =
      CurrentR(
         states[index],
         price
      );


   if(
      current_r <
      LOCK_TRIGGER_R
   )
      return;


   ApplyProfitLock(
      index
   );
}


//==================================================================
// MANAGE ALL POSITIONS
//==================================================================

void ManageAllPositions()
{
   for(
      int i = 0;
      i < ArraySize(states);
      i++
   )
   {
      if(
         PositionStillExists(
            states[i].position_id
         )
      )
      {
         ManagePosition(
            i
         );
      }
   }
}


//==================================================================
// POSITION NET PROFIT
//==================================================================

double PositionNetProfit(
   ulong position_id
)
{
   if(
      !HistorySelect(
         0,
         TimeCurrent()
      )
   )
      return 0.0;


   double net =
      0.0;


   int total =
      HistoryDealsTotal();


   for(
      int i = 0;
      i < total;
      i++
   )
   {
      ulong deal =
         HistoryDealGetTicket(
            i
         );


      if(
         deal == 0
      )
         continue;


      if(
         (ulong)
         HistoryDealGetInteger(
            deal,
            DEAL_POSITION_ID
         )
         !=
         position_id
      )
         continue;


      long entry_type =
         HistoryDealGetInteger(
            deal,
            DEAL_ENTRY
         );


      if(
         entry_type !=
         DEAL_ENTRY_OUT
         &&
         entry_type !=
         DEAL_ENTRY_OUT_BY
         &&
         entry_type !=
         DEAL_ENTRY_INOUT
      )
         continue;


      net +=
         HistoryDealGetDouble(
            deal,
            DEAL_PROFIT
         );


      net +=
         HistoryDealGetDouble(
            deal,
            DEAL_SWAP
         );


      net +=
         HistoryDealGetDouble(
            deal,
            DEAL_COMMISSION
         );
   }


   return net;
}


//==================================================================
// DEAL NET PROFIT
//==================================================================

double DealNetProfit(
   ulong deal
)
{
   if(
      deal == 0
   )
      return 0.0;


   double net =
      HistoryDealGetDouble(
         deal,
         DEAL_PROFIT
      );


   net +=
      HistoryDealGetDouble(
         deal,
         DEAL_SWAP
      );


   net +=
      HistoryDealGetDouble(
         deal,
         DEAL_COMMISSION
      );


   return net;
}


//==================================================================
// END PART 3A
//==================================================================//==================================================================
// PART 3B
// ROBUST EXIT LIFECYCLE + CHALLENGE + EA EVENTS
//==================================================================


//==================================================================
// EXIT PENDING STATE
//
// V2.2 problem:
// CleanOrphanStates() could remove a state before the corresponding
// exit transaction reached OnTradeTransaction.
//
// V2.3 solution:
// - OnTradeTransaction owns normal exit processing.
// - A closed position is NOT immediately deleted elsewhere.
// - Finalization is delayed briefly.
// - Backup cleanup only acts on genuinely stale orphan states.
//==================================================================

struct PendingFinalization
{
   bool active;

   ulong position_id;

   datetime detected_time;

   datetime last_deal_time;

   double accumulated_exit_profit;

   double last_exit_price;

   ulong last_exit_deal;
};


PendingFinalization pending_finalizations[];


//==================================================================
// FINALIZATION CONSTANTS
//==================================================================

const int FINALIZE_DELAY_SECONDS =
   2;


const int ORPHAN_GRACE_SECONDS =
   10;


//==================================================================
// FIND PENDING FINALIZATION
//==================================================================

int FindPendingFinalization(
   ulong position_id
)
{
   for(
      int i = 0;
      i < ArraySize(pending_finalizations);
      i++
   )
   {
      if(
         pending_finalizations[i].active
         &&
         pending_finalizations[i].position_id ==
         position_id
      )
         return i;
   }


   return -1;
}


//==================================================================
// REMOVE PENDING FINALIZATION
//==================================================================

void RemovePendingFinalization(
   int index
)
{
   int total =
      ArraySize(
         pending_finalizations
      );


   if(
      index < 0 ||
      index >= total
   )
      return;


   for(
      int i = index;
      i < total - 1;
      i++
   )
   {
      pending_finalizations[i] =
         pending_finalizations[i + 1];
   }


   ArrayResize(
      pending_finalizations,
      total - 1
   );
}


//==================================================================
// CREATE / UPDATE PENDING FINALIZATION
//==================================================================

void MarkPendingFinalization(
   ulong position_id,
   ulong deal,
   double deal_profit,
   double exit_price
)
{
   int index =
      FindPendingFinalization(
         position_id
      );


   if(
      index < 0
   )
   {
      PendingFinalization item;


      ZeroMemory(
         item
      );


      item.active =
         true;


      item.position_id =
         position_id;


      item.detected_time =
         TimeCurrent();


      item.last_deal_time =
         TimeCurrent();


      item.accumulated_exit_profit =
         deal_profit;


      item.last_exit_price =
         exit_price;


      item.last_exit_deal =
         deal;


      int size =
         ArraySize(
            pending_finalizations
         );


      ArrayResize(
         pending_finalizations,
         size + 1
      );


      pending_finalizations[size] =
         item;


      return;
   }


   pending_finalizations[index].last_deal_time =
      TimeCurrent();


   pending_finalizations[index].accumulated_exit_profit +=
      deal_profit;


   pending_finalizations[index].last_exit_price =
      exit_price;


   pending_finalizations[index].last_exit_deal =
      deal;
}


//==================================================================
// FINALIZE POSITION STATE
//==================================================================

bool FinalizePositionState(
   ulong position_id,
   string reason
)
{
   int state_index =
      FindStateByPositionId(
         position_id
      );


   if(
      state_index < 0
   )
   {
      LogDiag(
         "FINALIZE_STATE_MISSING",
         position_id,
         0.0,
         0.0,
         0.0,
         0,
         reason
      );


      return false;
   }


   // Never finalize a position that still exists.

   if(
      PositionStillExists(
         position_id
      )
   )
      return false;


   double net_profit =
      PositionNetProfit(
         position_id
      );


   LogTrade(
      "FINAL_CLOSE",
      states[state_index],
      net_profit,
      reason
   );


   RemoveState(
      state_index
   );


   return true;
}


//==================================================================
// PROCESS PENDING FINALIZATIONS
//==================================================================

void ProcessPendingFinalizations()
{
   for(
      int i =
      ArraySize(pending_finalizations) - 1;
      i >= 0;
      i--
   )
   {
      if(
         !pending_finalizations[i].active
      )
      {
         RemovePendingFinalization(
            i
         );


         continue;
      }


      ulong position_id =
         pending_finalizations[i].position_id;


      // Position still exists:
      // likely partial close / other deal.
      // Keep state alive.

      if(
         PositionStillExists(
            position_id
         )
      )
      {
         continue;
      }


      if(
         TimeCurrent() -
         pending_finalizations[i].last_deal_time
         <
         FINALIZE_DELAY_SECONDS
      )
      {
         continue;
      }


      bool finalized =
         FinalizePositionState(
            position_id,
            "Transaction-confirmed final close"
         );


      if(
         finalized
      )
      {
         RemovePendingFinalization(
            i
         );
      }
   }
}


//==================================================================
// BACKUP ORPHAN FINALIZER
//
// This is deliberately conservative.
//
// Unlike V2.2, it does NOT immediately delete states when a position
// disappears.
//
// It waits for transaction processing first.
//==================================================================

void ProcessStaleOrphanStates()
{
   datetime now =
      TimeCurrent();


   for(
      int i =
      ArraySize(states) - 1;
      i >= 0;
      i--
   )
   {
      ulong position_id =
         states[i].position_id;


      if(
         PositionStillExists(
            position_id
         )
      )
         continue;


      // If transaction lifecycle already owns this close,
      // do nothing here.

      if(
         FindPendingFinalization(
            position_id
         )
         >= 0
      )
         continue;


      // We use the last known position/open time only as a safety
      // check. A newly opened position should never be treated as an
      // orphan immediately.

      if(
         now -
         states[i].open_time
         <
         ORPHAN_GRACE_SECONDS
      )
         continue;


      // Search history for an actual exit deal.

      if(
         !HistorySelect(
            states[i].open_time -
            60,
            now
         )
      )
         continue;


      bool exit_found =
         false;


      datetime newest_exit_time =
         0;


      double newest_exit_price =
         0.0;


      int deals =
         HistoryDealsTotal();


      for(
         int d = 0;
         d < deals;
         d++
      )
      {
         ulong deal =
            HistoryDealGetTicket(
               d
            );


         if(
            deal == 0
         )
            continue;


         if(
            (ulong)
            HistoryDealGetInteger(
               deal,
               DEAL_POSITION_ID
            )
            !=
            position_id
         )
            continue;


         long entry_type =
            HistoryDealGetInteger(
               deal,
               DEAL_ENTRY
            );


         if(
            entry_type !=
            DEAL_ENTRY_OUT
            &&
            entry_type !=
            DEAL_ENTRY_OUT_BY
            &&
            entry_type !=
            DEAL_ENTRY_INOUT
         )
            continue;


         datetime deal_time =
            (datetime)
            HistoryDealGetInteger(
               deal,
               DEAL_TIME
            );


         if(
            deal_time >=
            newest_exit_time
         )
         {
            newest_exit_time =
               deal_time;


            newest_exit_price =
               HistoryDealGetDouble(
                  deal,
                  DEAL_PRICE
               );
         }


         exit_found =
            true;
      }


      if(
         !exit_found
      )
         continue;


      if(
         now -
         newest_exit_time
         <
         ORPHAN_GRACE_SECONDS
      )
         continue;


      UpdateExcursionFromPrice(
         i,
         newest_exit_price
      );


      LogDiag(
         "ORPHAN_BACKUP",
         position_id,
         newest_exit_price,
         0.0,
         0.0,
         0,
         "Backup finalizer used after transaction grace period"
      );


      double net_profit =
         PositionNetProfit(
            position_id
         );


      LogTrade(
         "FINAL_CLOSE",
         states[i],
         net_profit,
         "Backup orphan finalization"
      );


      RemoveState(
         i
      );
   }
}


//==================================================================
// CLOSE ALL BOT POSITIONS
//==================================================================

void CloseAllBotPositions(
   string reason
)
{
   trade.SetExpertMagicNumber(
      MAGIC
   );


   for(
      int i =
      PositionsTotal() - 1;
      i >= 0;
      i--
   )
   {
      ulong ticket =
         PositionGetTicket(
            i
         );


      if(
         ticket == 0
      )
         continue;


      if(
         !PositionSelectByTicket(
            ticket
         )
      )
         continue;


      if(
         PositionGetString(
            POSITION_SYMBOL
         )
         !=
         SYMBOL_NAME
      )
         continue;


      if(
         PositionGetInteger(
            POSITION_MAGIC
         )
         !=
         (long)MAGIC
      )
         continue;


      ulong position_id =
         (ulong)
         PositionGetInteger(
            POSITION_IDENTIFIER
         );


      ResetLastError();


      bool result =
         trade.PositionClose(
            ticket
         );


      ulong retcode =
         trade.ResultRetcode();


      LogDiag(
         result
         ?
         "FORCED_CLOSE"
         :
         "FORCED_CLOSE_FAIL",

         position_id,

         AccountInfoDouble(
            ACCOUNT_EQUITY
         ),

         day_start_equity,

         account_start_equity,

         retcode,

         reason
      );
   }
}


//==================================================================
// CHALLENGE PROTECTION
//==================================================================

void EnforceChallengeProtection()
{
   if(
      !ChallengeMode
   )
      return;


   double equity =
      AccountInfoDouble(
         ACCOUNT_EQUITY
      );


   if(
      equity <= 0.0
   )
      return;


   if(
      account_start_equity <= 0.0
      ||
      day_start_equity <= 0.0
   )
      return;


   double total_loss_pct =
      (
         account_start_equity -
         equity
      )
      /
      account_start_equity
      *
      100.0;


   double daily_loss_pct =
      (
         day_start_equity -
         equity
      )
      /
      day_start_equity
      *
      100.0;


   bool daily_breach =
      daily_loss_pct >=
      ChallengeDailyStopPct();


   bool total_breach =
      total_loss_pct >=
      ChallengeTotalStopPct();


   if(
      !daily_breach
      &&
      !total_breach
   )
      return;


   ResetSetup();


   string reason =
      daily_breach
      ?
      "Challenge daily safety stop"
      :
      "Challenge total safety stop";


   if(
      BotPositionCount() > 0
   )
   {
      CloseAllBotPositions(
         reason
      );
   }
}


//==================================================================
// ON TRADE TRANSACTION
//
// This is now the PRIMARY owner of exit events.
//
// State is NOT deleted here immediately.
// We first log the deal and mark the position for delayed
// finalization.
//==================================================================

void OnTradeTransaction(
   const MqlTradeTransaction &trans,
   const MqlTradeRequest &request,
   const MqlTradeResult &result
)
{
   if(
      trans.type !=
      TRADE_TRANSACTION_DEAL_ADD
   )
      return;


   ulong deal =
      trans.deal;


   if(
      deal == 0
   )
      return;


   if(
      !HistoryDealSelect(
         deal
      )
   )
      return;


   string symbol =
      HistoryDealGetString(
         deal,
         DEAL_SYMBOL
      );


   if(
      symbol !=
      SYMBOL_NAME
   )
      return;


   long magic =
      HistoryDealGetInteger(
         deal,
         DEAL_MAGIC
      );


   if(
      magic !=
      (long)MAGIC
   )
      return;


   ulong position_id =
      (ulong)
      HistoryDealGetInteger(
         deal,
         DEAL_POSITION_ID
      );


   long entry_type =
      HistoryDealGetInteger(
         deal,
         DEAL_ENTRY
      );


   //===============================================================
   // ENTRY DEAL
   //===============================================================

   if(
      entry_type ==
      DEAL_ENTRY_IN
   )
   {
      // Position may already be visible at this point.
      // If not, SyncPositionState on the next tick/timer will catch it.

      RegisterLivePosition();


      return;
   }


   //===============================================================
   // EXIT DEAL
   //===============================================================

   if(
      entry_type !=
      DEAL_ENTRY_OUT
      &&
      entry_type !=
      DEAL_ENTRY_OUT_BY
      &&
      entry_type !=
      DEAL_ENTRY_INOUT
   )
      return;


   int state_index =
      FindStateByPositionId(
         position_id
      );


   // If the state is unexpectedly absent, attempt one registration.
   // This should only matter for unusual event sequencing/restarts.

   if(
      state_index < 0
   )
   {
      RegisterLivePosition();


      state_index =
         FindStateByPositionId(
            position_id
         );
   }


   if(
      state_index < 0
   )
   {
      LogDiag(
         "EXIT_STATE_MISSING",
         position_id,
         trans.price,
         DealNetProfit(
            deal
         ),
         0.0,
         result.retcode,
         "Exit deal arrived without matching state"
      );


      return;
   }


   double exit_price =
      HistoryDealGetDouble(
         deal,
         DEAL_PRICE
      );


   double deal_profit =
      DealNetProfit(
         deal
      );


   UpdateExcursionFromPrice(
      state_index,
      exit_price
   );


   LogTrade(
      "CLOSE_DEAL",
      states[state_index],
      deal_profit,
      "Exit deal received"
   );


   MarkPendingFinalization(
      position_id,
      deal,
      deal_profit,
      exit_price
   );
}


//==================================================================
// INITIALIZE EXISTING POSITION
//
// Used after EA restart.
// Research backtests normally start flat.
//==================================================================

void RecoverExistingPosition()
{
   if(
      BotPositionCount() <= 0
   )
      return;


   ResetPendingSignal();


   RegisterLivePosition();
}


//==================================================================
// INITIALIZATION
//==================================================================

int OnInit()
{
   if(
      !SymbolSelect(
         SYMBOL_NAME,
         true
      )
   )
   {
      Print(
         EA_NAME,
         ": unable to select ",
         SYMBOL_NAME
      );


      return INIT_FAILED;
   }


   trade.SetExpertMagicNumber(
      MAGIC
   );


   trade.SetTypeFillingBySymbol(
      SYMBOL_NAME
   );


   trade.SetAsyncMode(
      false
   );


   ResetSetup();


   ResetPendingSignal();


   ArrayResize(
      states,
      0
   );


   ArrayResize(
      pending_finalizations,
      0
   );


   ArrayResize(
      entry_times,
      0
   );


   account_start_equity =
      AccountInfoDouble(
         ACCOUNT_EQUITY
      );


   day_start_equity =
      account_start_equity;


   current_day_key =
      DayKey();


   last_m5_bar =
      iTime(
         SYMBOL_NAME,
         TF_ENTRY,
         0
      );


   OpenLogFiles();


   RecoverExistingPosition();


   EventSetTimer(
      2
   );


   Print(
      EA_NAME,
      " initialized. BUILD=EXTVAL_F7_CORE_20260908 | Risk=",
      DoubleToString(
         RiskPct,
         2
      ),
      "% | Management=",
      EnumToString(Management),
      " | Sessions=Asia+London | NY=OFF | ChallengeGuards=OFF"
   );


   return INIT_SUCCEEDED;
}


//==================================================================
// DEINITIALIZATION
//==================================================================

void OnDeinit(
   const int reason
)
{
   EventKillTimer();


   ProcessPendingFinalizations();


   CloseLogFiles();


   Print(
      EA_NAME,
      " deinitialized. Reason=",
      reason
   );
}


//==================================================================
// MAIN TICK
//==================================================================

void OnTick()
{
   UpdateDayBaseline();


   SyncPositionState();


   UpdateAllExcursions();


   EnforceChallengeProtection();


   ManageAllPositions();


   // Transaction finalization gets priority.

   ProcessPendingFinalizations();


   // Conservative emergency fallback only.

   ProcessStaleOrphanStates();


   RunEntryEngine();
}


//==================================================================
// TIMER
//==================================================================

void OnTimer()
{
   UpdateDayBaseline();


   SyncPositionState();


   UpdateAllExcursions();


   EnforceChallengeProtection();


   ManageAllPositions();


   ProcessPendingFinalizations();


   ProcessStaleOrphanStates();


   RunEntryEngine();
}


//==================================================================
// END XAU VELOCITY V2.3
//==================================================================