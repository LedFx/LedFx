import { useState } from 'react'
import { Button } from '@mui/material'
import Tour from 'reactour'
import { Info } from '@mui/icons-material'
import useStore from '../../store/useStore'

const step = ({ title = 'Title', text = 'Text', number = 0 }) => ({
  selector: `.step-effect-${number}`,
  content: (
    <div>
      <h2>{title}</h2>
      {text}
    </div>
  ),
  style: {
    backgroundColor: '#303030'
  }
})

const TourEffect = ({ schemaProperties }: any) => {
  const [isTourOpen, setIsTourOpen] = useState(false)
  const setTour = useStore((state) => state.setTour)

  const steps = schemaProperties.map((p: any, i: number) =>
    step({
      title: p.title,
      text: p.description,
      number: i
    })
  )

  return (
    <>
      <Button
        onClick={() => {
          setIsTourOpen(true)
          setTour('effect')
        }}
        style={{ marginRight: '.5rem' }}
        className="step-device-seven"
      >
        <Info />
      </Button>
      <Tour
        steps={steps}
        accentColor="#800000"
        isOpen={isTourOpen}
        showNavigation={false}
        // badgeContent={()=><Info size="small" />}
        onRequestClose={() => setIsTourOpen(false)}
        showNumber={false}
      />
    </>
  )
}

export default TourEffect
