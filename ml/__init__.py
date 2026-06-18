# ML prediction modules for 双色球
# 模块已归档至 ml/_deprecated/ — 仅保留活跃模块
# 归档模块: xgb_predictor, lstm_predictor, transformer_predictor, thompson_sampler
#           advanced, arbitrage_engine, compressed_sensing, ewc_soup, hmm_regime,
#           negative_selection, nonlinear_dynamics, self_trainer, sirius_optimizer,
#           sobol_engine, training_optimizers, predictors/
from .micro_portfolio import generate_tickets, rule_status
from .covering_design import generate_candidate_set, build_covering_tickets, lottery_ev_calculator
from .prize_evaluator import evaluate_strategy_tickets
