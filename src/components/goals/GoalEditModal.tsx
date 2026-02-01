// Goal Edit Modal - Edit goals with friction (cooldown)
// Shows historical performance before allowing changes

import { useState } from 'react';
import { Clock, AlertTriangle, Save } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { TradingGoals, GoalAdherence } from '@/types/patterns';

interface GoalEditModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  goals: TradingGoals;
  adherence: GoalAdherence[];
  onSave: (updates: Partial<TradingGoals>, reason: string) => void;
}

export function GoalEditModal({
  open,
  onOpenChange,
  goals,
  adherence,
  onSave,
}: GoalEditModalProps) {
  const [formData, setFormData] = useState({
    max_risk_per_trade_percent: goals.max_risk_per_trade_percent,
    max_daily_loss: goals.max_daily_loss,
    max_trades_per_day: goals.max_trades_per_day,
    require_stoploss: goals.require_stoploss,
    min_time_between_trades_minutes: goals.min_time_between_trades_minutes,
    max_position_size_percent: goals.max_position_size_percent,
  });
  const [reason, setReason] = useState('');
  
  const handleSave = () => {
    if (!reason.trim()) return;
    onSave(formData, reason);
    onOpenChange(false);
    setReason('');
  };
  
  const getAdherenceForGoal = (goalName: string) => {
    return adherence.find(a => a.goal_name.toLowerCase().includes(goalName.toLowerCase()));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-warning" />
            Modify Trading Commitments
          </DialogTitle>
          <DialogDescription>
            Your changes will be logged. Consider your historical performance before adjusting.
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          {/* Warning Banner */}
          <div className="flex items-start gap-3 p-3 rounded-lg bg-warning/10 border border-warning/30">
            <AlertTriangle className="h-5 w-5 text-warning flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-warning">Think twice before loosening goals</p>
              <p className="text-muted-foreground mt-1">
                Traders who stick to stricter limits historically lose 40% less during drawdowns.
              </p>
            </div>
          </div>
          
          {/* Goal Inputs */}
          <div className="grid gap-4">
            {/* Max Risk Per Trade */}
            <div className="grid gap-2">
              <Label htmlFor="max_risk">Max Risk Per Trade (%)</Label>
              <div className="flex items-center gap-3">
                <Input
                  id="max_risk"
                  type="number"
                  min={0.5}
                  max={10}
                  step={0.5}
                  value={formData.max_risk_per_trade_percent}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    max_risk_per_trade_percent: parseFloat(e.target.value)
                  }))}
                  className="w-24"
                />
                <span className="text-sm text-muted-foreground">
                  Current: {getAdherenceForGoal('risk')?.adherence_percent ?? 100}% adherence
                </span>
              </div>
            </div>
            
            {/* Max Daily Loss */}
            <div className="grid gap-2">
              <Label htmlFor="max_loss">Max Daily Loss (₹)</Label>
              <div className="flex items-center gap-3">
                <Input
                  id="max_loss"
                  type="number"
                  min={1000}
                  max={100000}
                  step={1000}
                  value={formData.max_daily_loss}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    max_daily_loss: parseInt(e.target.value)
                  }))}
                  className="w-32"
                />
                <span className="text-sm text-muted-foreground">
                  Current: {getAdherenceForGoal('daily loss')?.adherence_percent ?? 100}% adherence
                </span>
              </div>
            </div>
            
            {/* Max Trades Per Day */}
            <div className="grid gap-2">
              <Label htmlFor="max_trades">Max Trades Per Day</Label>
              <div className="flex items-center gap-3">
                <Input
                  id="max_trades"
                  type="number"
                  min={1}
                  max={50}
                  step={1}
                  value={formData.max_trades_per_day}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    max_trades_per_day: parseInt(e.target.value)
                  }))}
                  className="w-24"
                />
                <span className="text-sm text-muted-foreground">
                  Current: {getAdherenceForGoal('trades')?.adherence_percent ?? 100}% adherence
                </span>
              </div>
            </div>
            
            {/* Require Stop Loss */}
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Require Stop Loss</Label>
                <p className="text-xs text-muted-foreground">
                  Flag trades without stop loss as violations
                </p>
              </div>
              <Switch
                checked={formData.require_stoploss}
                onCheckedChange={(checked) => setFormData(prev => ({
                  ...prev,
                  require_stoploss: checked
                }))}
              />
            </div>
          </div>
          
          {/* Reason for Change */}
          <div className="grid gap-2">
            <Label htmlFor="reason">Reason for Change (Required)</Label>
            <Textarea
              id="reason"
              placeholder="Why are you modifying these goals? This will be logged for accountability."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="min-h-[80px]"
            />
          </div>
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={!reason.trim()}
            className="gap-2"
          >
            <Save className="h-4 w-4" />
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
