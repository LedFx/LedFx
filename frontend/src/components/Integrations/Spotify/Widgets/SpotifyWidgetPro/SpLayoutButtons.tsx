import { styled } from '@mui/material/styles'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import ToggleButton from '@mui/material/ToggleButton'
import {
  PanoramaHorizontalSelect,
  PanoramaVerticalSelect
  // PanoramaWideAngleSelect,
} from '@mui/icons-material'
import useStore from '../../../../../store/useStore'

const ButtonGroup = styled(ToggleButtonGroup)(({ theme }) => ({
  '& .MuiToggleButtonGroup-grouped': {
    margin: theme.spacing(0.5),
    border: 0,
    color: '#444',
    '&.Mui-disabled': {
      border: 0
    },
    '&:not(:first-of-type)': {
      borderRadius: theme.shape.borderRadius
    },
    '&:first-of-type': {
      borderRadius: theme.shape.borderRadius
    },
    '&.Mui-selected': {
      color: '#ddd'
    }
  }
}))

export default function SpLayoutButtons() {
  const swSize = useStore((state) => state.spotify.swSize)
  const setSwSize = useStore((state) => state.setSwSize)

  const setSwWidth = useStore((state) => state.setSwWidth)
  const swX = useStore((state) => state.spotify.swX)
  const setSwX = useStore((state) => state.setSwX)
  const swY = useStore((state) => state.spotify.swY)
  const setSwY = useStore((state) => state.setSwY)

  const settingSize = (newSize: string) => {
    if (newSize === 'large') {
      setSwWidth(960)
      setSwX(Math.max(swX - 660, 0))
      setSwY(swY + 150)
    }
    if (newSize === 'small') {
      setSwWidth(300)
      setSwX(swX + 660)
      setSwY(Math.max(swY - 150, 0))
    }
    setSwSize(newSize)
  }
  const handleAlignment = (
    event: React.MouseEvent<HTMLElement>,
    newSize: string | null
  ) => {
    if (newSize !== null) {
      settingSize(newSize)
    }
  }

  return (
    <ButtonGroup
      value={swSize}
      exclusive
      onChange={handleAlignment}
      aria-label="text alignment"
    >
      <ToggleButton value="small" aria-label="small">
        <PanoramaVerticalSelect />
      </ToggleButton>
      {/* <ToggleButton value="medium" aria-label="medium">
                  <PanoramaWideAngleSelect />
                </ToggleButton> */}
      <ToggleButton value="large" aria-label="large">
        <PanoramaHorizontalSelect />
      </ToggleButton>
    </ButtonGroup>
  )
}
