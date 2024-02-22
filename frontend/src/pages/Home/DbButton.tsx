import { Button } from '@mui/material'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'

const DbButton = ({
  onClick,
  icon,
  text
}: {
  onClick: (e: any) => typeof e
  icon: string | undefined
  text: string | undefined
}) => {
  return (
    <Button
      onClick={onClick}
      variant="text"
      startIcon={
        <BladeIcon
          name={icon}
          style={icon === 'wled' ? { marginTop: -4 } : {}}
        />
      }
      size="large"
      sx={{
        textTransform: 'none',
        justifyContent: 'flex-start',
        ml: 1,
        '& .MuiButton-startIcon': {
          mr: 3
        }
      }}
    >
      {text}
    </Button>
  )
}

export default DbButton
