import DropDown from './DropDown'

export interface EffectDropDownProps {
  effects: any
  virtual: any
  features: any
  setEffect: any
  getVirtuals: any
}

const EffectDropDown = ({
  effects,
  virtual,
  features,
  setEffect,
  getVirtuals
}: EffectDropDownProps) => {
  const effectNames =
    effects &&
    Object.keys(effects).map((eid) => ({
      name: effects[eid].name,
      id: effects[eid].id,
      category: effects[eid].category
    }))

  const groups =
    effectNames &&
    effectNames.reduce((r: any, a: any) => {
      // eslint-disable-next-line no-param-reassign
      r[a.category] = [...(r[a.category] || []), a]
      return r
    }, {})

  const onEffectTypeChange = (e: any) =>
    setEffect(virtual.id, e.target.value).then(() => {
      getVirtuals()
    })

  return (
    <DropDown
      value={(virtual && virtual.effect && virtual.effect.type) || ''}
      onChange={(e: any) => onEffectTypeChange(e)}
      groups={groups}
      showFilter={features.effectfilter}
      title="Effect Type"
    />
  )
}

export default EffectDropDown
