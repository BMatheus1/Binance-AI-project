const reasons:Record<string,string> = {
  frozen_signal_not_up:"O sinal congelado não indica compra",
  up_probability_below_frozen_threshold:"Probabilidade abaixo do limiar congelado",
  market_temporal_integrity_or_freshness:"Aguardando dados atuais e temporalmente válidos",
  market_data_incomplete:"Dados de mercado incompletos",
  forecast_unavailable:"Previsão indisponível para este ativo",
  invalid_executable_quote:"Cotação executável inválida ou ausente",
  frozen_model_scope_is_btc_only:"Modelo congelado disponível somente para Bitcoin",
  model_scope_unavailable_for_asset:"Não há modelo validado para este ativo",
  invalid_probability_distribution:"Distribuição probabilística inválida",
  spread_limit:"Spread acima do limite ou indisponível",
  depth_limit:"Liquidez abaixo do limite ou indisponível",
  frozen_experimental_signal_eligible:"Sinal experimental elegível; sujeito à autorização e ao risco",
  quantitative_threshold_abstention:"Limiar quantitativo não atingido",
  quantitative_signal_not_long:"Previsão quantitativa não indica compra",
  expected_gross_return_not_live_calibrated:"Magnitude do retorno ainda não calibrada",
  no_positive_net_edge:"Sem evidência de vantagem líquida após custos",
  incomplete_market_data:"Dados de mercado incompletos",news_risk_veto:"Veto de risco por notícias",
  trend_continuation:"Continuação de tendência",pullback:"Recuo em tendência",
  breakout:"Rompimento",mean_reversion:"Retorno à média",volatility_expansion:"Expansão de volatilidade",
  momentum_acceleration:"Aceleração do movimento",book_imbalance:"Desequilíbrio do livro",
};
export function reasonLabel(reason:string):string {return reasons[reason]??`Código técnico: ${reason}`;}
export function decisionLabel(value:string):string {
  return ({COMPRAR:"Proposta de compra",NAO_COMPRAR:"Não comprar",AGUARDAR_DADOS:"Aguardar dados",INDISPONIVEL_SEGURANCA:"Indisponível por segurança",abstain:"Abstenção",buy:"Compra"} as Record<string,string>)[value]??value;
}
export function stateLabel(value:string):string {
  if(value==="DEMO_AUTONOMOUS_EXPERIMENTAL")return "Demo experimental";
  return ({ready:"Disponível",unavailable:"Indisponível",available_not_loaded:"Disponível, ainda não carregado",loading:"Carregando",degraded:"Degradado",connected:"Conectado",disconnected:"Desconectado",OBSERVE:"Observação",EXPERIMENTAL_DEMO:"Demo experimental",healthy:"Saudável",retry_wait:"Aguardando nova tentativa",blocked:"Bloqueado",prepared:"Preparada",authorized:"Autorizada",running:"Em execução",OPEN:"Aberta",CLOSED:"Encerrada",RECOVERY_REQUIRED:"Recuperação necessária"} as Record<string,string>)[value]??"Aguardando verificação";
}
export function eventLabel(value:string):string {
  return ({engine_started:"Motor iniciado",reconciliation_completed:"Reconciliação concluída",reconciliation_failed:"Falha de reconciliação",entry_abstention:"Compra rejeitada",risk_approved:"Risco aprovado",demo_position_opened:"Posição aberta",demo_position_closed:"Posição encerrada",session_prepared:"Sessão preparada",session_stopped:"Sessão encerrada",session_authorized:"Sessão autorizada",entry_failure:"Falha ao abrir posição"} as Record<string,string>)[value]??"Evento operacional · consulte os detalhes";
}
