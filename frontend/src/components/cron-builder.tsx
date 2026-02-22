import { useState, useEffect } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface CronBuilderProps {
  value: string
  onChange: (value: string) => void
}

type Frequency = "daily" | "weekly" | "monthly" | "custom"

const DAYS_OF_WEEK = [
  { label: "Sun", value: 0 },
  { label: "Mon", value: 1 },
  { label: "Tue", value: 2 },
  { label: "Wed", value: 3 },
  { label: "Thu", value: 4 },
  { label: "Fri", value: 5 },
  { label: "Sat", value: 6 },
]

export function CronBuilder({ value, onChange }: CronBuilderProps) {
  const [frequency, setFrequency] = useState<Frequency>("daily")
  const [hour, setHour] = useState(0)
  const [minute, setMinute] = useState(0)
  const [weekDays, setWeekDays] = useState<number[]>([])
  const [monthDay, setMonthDay] = useState(1)
  const [customCron, setCustomCron] = useState(value)

  // Parse initial value
  useEffect(() => {
    if (!value) return

    const parts = value.split(" ")
    if (parts.length !== 5) {
      setFrequency("custom")
      setCustomCron(value)
      return
    }

    const [m, h, dom, mon, dow] = parts

    // Helper to compare arrays specifically for useEffect bail-out
    const arraysEqual = (a: number[], b: number[]) => 
      JSON.stringify([...a].sort((x,y)=>x-y)) === JSON.stringify([...b].sort((x,y)=>x-y))

    if (dom === "*" && mon === "*" && dow === "*") {
      // Daily
      if (frequency !== "daily") setFrequency("daily")
      if (minute !== (parseInt(m) || 0)) setMinute(parseInt(m) || 0)
      if (hour !== (parseInt(h) || 0)) setHour(parseInt(h) || 0)
    } else if (dom === "*" && mon === "*" && dow !== "*") {
      // Weekly
      const parsedDays = dow.split(",").map(d => parseInt(d)).filter(n => !isNaN(n))
      
      if (frequency !== "weekly") setFrequency("weekly")
      if (minute !== (parseInt(m) || 0)) setMinute(parseInt(m) || 0)
      if (hour !== (parseInt(h) || 0)) setHour(parseInt(h) || 0)
      setWeekDays(prev => arraysEqual(prev, parsedDays) ? prev : parsedDays)
    } else if (dom !== "*" && mon === "*" && dow === "*") {
      // Monthly
      if (frequency !== "monthly") setFrequency("monthly")
      if (minute !== (parseInt(m) || 0)) setMinute(parseInt(m) || 0)
      if (hour !== (parseInt(h) || 0)) setHour(parseInt(h) || 0)
      if (monthDay !== (parseInt(dom) || 1)) setMonthDay(parseInt(dom) || 1)
    } else {
      if (frequency !== "custom") setFrequency("custom")
      if (customCron !== value) setCustomCron(value)
    }
  }, [value]) // Only depend on value

  // Helper to generate cron and notify parent
  const notifyChange = (
    newFreq: Frequency, 
    newHour: number, 
    newMinute: number, 
    newWeekDays: number[], 
    newMonthDay: number,
    newCustom: string
  ) => {
    let newCron = ""
    if (newFreq === "daily") {
      newCron = `${newMinute} ${newHour} * * *`
    } else if (newFreq === "weekly") {
      const dow = newWeekDays.length > 0 ? [...newWeekDays].sort((a, b) => a - b).join(",") : "*"
      newCron = `${newMinute} ${newHour} * * ${dow}`
    } else if (newFreq === "monthly") {
      newCron = `${newMinute} ${newHour} ${newMonthDay} * *`
    } else {
      newCron = newCustom
    }
    
    if (newCron !== value) {
      onChange(newCron)
    }
  }

  // Event Handlers
  const handleFrequencyChange = (v: Frequency) => {
    setFrequency(v)
    notifyChange(v, hour, minute, weekDays, monthDay, customCron)
  }

  const handleTimeChange = (type: 'hour' | 'minute', val: number) => {
    const newHour = type === 'hour' ? val : hour
    const newMinute = type === 'minute' ? val : minute
    if (type === 'hour') setHour(newHour)
    else setMinute(newMinute)
    notifyChange(frequency, newHour, newMinute, weekDays, monthDay, customCron)
  }

  const handleWeekDayChange = (dayValue: number, checked: boolean) => {
    let newDays = [...weekDays]
    if (checked) {
      if (!newDays.includes(dayValue)) newDays.push(dayValue)
    } else {
      newDays = newDays.filter(d => d !== dayValue)
    }
    setWeekDays(newDays)
    notifyChange(frequency, hour, minute, newDays, monthDay, customCron)
  }

  const handleMonthDayChange = (val: number) => {
    setMonthDay(val)
    notifyChange(frequency, hour, minute, weekDays, val, customCron)
  }

  const handleCustomChange = (val: string) => {
    setCustomCron(val)
    notifyChange("custom", hour, minute, weekDays, monthDay, val)
  }

  return (
    <div className="space-y-4 rounded-md border p-4 bg-muted/20">
      <div className="flex items-center gap-4">
        <Label>Frequency</Label>
        <Select
          value={frequency}
          onValueChange={(v) => handleFrequencyChange(v as Frequency)}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="daily">Daily</SelectItem>
            <SelectItem value="weekly">Weekly</SelectItem>
            <SelectItem value="monthly">Monthly</SelectItem>
            <SelectItem value="custom">Custom (Advanced)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {frequency !== "custom" && (
        <div className="flex items-center gap-4">
          <Label>Time</Label>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              min={0}
              max={23}
              className="w-16"
              value={hour}
              onChange={(e) => handleTimeChange('hour', Math.min(23, Math.max(0, parseInt(e.target.value) || 0)))}
            />
            <span>:</span>
            <Input
              type="number"
              min={0}
              max={59}
              className="w-16"
              value={minute}
              onChange={(e) => handleTimeChange('minute', Math.min(59, Math.max(0, parseInt(e.target.value) || 0)))}
            />
          </div>
        </div>
      )}

      {frequency === "weekly" && (
        <div className="space-y-2">
          <Label>Days of Week</Label>
          <div className="flex flex-wrap gap-2">
            {DAYS_OF_WEEK.map((day) => (
              <div key={day.value} className="flex items-center space-x-2 border rounded p-2">
                <Checkbox
                  id={`day-${day.value}`}
                  checked={weekDays.includes(day.value)}
                  onCheckedChange={(checked) => handleWeekDayChange(day.value, checked as boolean)}
                />
                <label
                  htmlFor={`day-${day.value}`}
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                >
                  {day.label}
                </label>
              </div>
            ))}
          </div>
        </div>
      )}

      {frequency === "monthly" && (
        <div className="flex items-center gap-4">
          <Label>Day of Month</Label>
          <Input
            type="number"
            min={1}
            max={31}
            className="w-16"
            value={monthDay}
            onChange={(e) => handleMonthDayChange(Math.min(31, Math.max(1, parseInt(e.target.value) || 1)))}
          />
        </div>
      )}

      {frequency === "custom" && (
        <div className="space-y-2">
          <Label>Cron Expression</Label>
          <Input
            value={customCron}
            onChange={(e) => handleCustomChange(e.target.value)}
            placeholder="* * * * *"
          />
          <p className="text-xs text-muted-foreground">
            Format: &lt;minute&gt; &lt;hour&gt; &lt;day-of-month&gt; &lt;month&gt; &lt;day-of-week&gt;
          </p>
        </div>
      )}

      <div className="pt-2 border-t text-xs text-muted-foreground">
        Result: <span className="font-mono bg-muted px-1 rounded">{value}</span>
      </div>
    </div>
  )
}
