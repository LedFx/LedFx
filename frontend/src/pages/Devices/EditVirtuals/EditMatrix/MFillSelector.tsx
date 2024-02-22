import { Chip, Divider, MenuItem, Select } from '@mui/material'
import BladeFrame from '../../../../components/SchemaForm/components/BladeFrame'
import right from '../../../../assets/right.svg'
import rightSnake from '../../../../assets/right-snake.svg'
import rightFlip from '../../../../assets/right-flip.svg'
import rightSnakeFlip from '../../../../assets/right-snake-flip.svg'
import bottom from '../../../../assets/bottom.svg'
import bottomFlip from '../../../../assets/bottom-flip.svg'
import bottomSnake from '../../../../assets/bottom-snake.svg'
import bottomSnakeFlip from '../../../../assets/bottom-snake-flip.svg'
import left from '../../../../assets/left.svg'
import leftSnake from '../../../../assets/left-snake.svg'
import leftFlip from '../../../../assets/left-flip.svg'
import leftSnakeFlip from '../../../../assets/left-snake-flip.svg'
import top from '../../../../assets/top.svg'
import topSnake from '../../../../assets/top-snake.svg'
import topFlip from '../../../../assets/top-flip.svg'
import topSnakeFlip from '../../../../assets/top-snake-flip.svg'
import type { IDir } from './M.utils'

const MFillSelector = ({
  direction,
  onChange
}: {
  direction: IDir
  onChange: any
}) => {
  return (
    <BladeFrame
      title="Fill Direction"
      full={false}
      style={{ marginBottom: '1rem' }}
    >
      <Select
        value={direction}
        variant="standard"
        fullWidth
        MenuProps={{
          PaperProps: {
            style: {
              maxHeight: 300
            }
          }
        }}
        onChange={(e) => onChange(e.target.value)}
      >
        <MenuItem sx={{ justifyContent: 'space-between' }} value="right">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Linear
              <Chip size="small" label="Right" variant="outlined" />
              <Chip size="small" label="Down" variant="outlined" />
            </div>
            <img width="30px" src={right} alt="rightSnake" />
          </div>
        </MenuItem>
        <MenuItem sx={{ justifyContent: 'space-between' }} value="right-flip">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Linear
              <Chip size="small" label="Right" variant="outlined" />
              <Chip size="small" label="Up" variant="outlined" />
            </div>
            <img width="30px" src={rightFlip} alt="rightFlip" />
          </div>
        </MenuItem>
        <MenuItem sx={{ justifyContent: 'space-between' }} value="right-snake">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Snake
              <Chip size="small" label="Right" variant="outlined" />
              <Chip size="small" label="Down" variant="outlined" />
            </div>
            <img width="30px" src={rightSnake} alt="rightSnake" />
          </div>
        </MenuItem>
        <MenuItem
          sx={{ justifyContent: 'space-between' }}
          value="right-snake-flip"
        >
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Snake
              <Chip size="small" label="Right" variant="outlined" />
              <Chip size="small" label="Up" variant="outlined" />
            </div>
            <img width="30px" src={rightSnakeFlip} alt="rightSnakeFlip" />
          </div>
        </MenuItem>
        <Divider />
        <MenuItem sx={{ justifyContent: 'space-between' }} value="bottom">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Linear
              <Chip size="small" label="Down" variant="outlined" />
              <Chip size="small" label="Right" variant="outlined" />
            </div>
            <img width="30px" src={bottom} alt="bottomSnake" />
          </div>
        </MenuItem>
        <MenuItem sx={{ justifyContent: 'space-between' }} value="bottom-flip">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Linear
              <Chip size="small" label="Down" variant="outlined" />
              <Chip size="small" label="Left" variant="outlined" />
            </div>
            <img width="30px" src={bottomFlip} alt="bottomSnakeFlip" />
          </div>
        </MenuItem>
        <MenuItem sx={{ justifyContent: 'space-between' }} value="bottom-snake">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Snake
              <Chip size="small" label="Down" variant="outlined" />
              <Chip size="small" label="Right" variant="outlined" />
            </div>
            <img width="30px" src={bottomSnake} alt="bottomSnake" />
          </div>
        </MenuItem>
        <MenuItem
          sx={{ justifyContent: 'space-between' }}
          value="bottom-snake-flip"
        >
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Snake
              <Chip size="small" label="Down" variant="outlined" />
              <Chip size="small" label="Left" variant="outlined" />
            </div>
            <img width="30px" src={bottomSnakeFlip} alt="bottomSnakeFlip" />
          </div>
        </MenuItem>
        <Divider />
        <MenuItem sx={{ justifyContent: 'space-between' }} value="left-flip">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Linear
              <Chip size="small" label="Left" variant="outlined" />
              <Chip size="small" label="Down" variant="outlined" />
            </div>
            <img width="30px" src={leftFlip} alt="leftFlip" />
          </div>
        </MenuItem>
        <MenuItem sx={{ justifyContent: 'space-between' }} value="left">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Linear
              <Chip size="small" label="Left" variant="outlined" />
              <Chip size="small" label="Up" variant="outlined" />
            </div>
            <img width="30px" src={left} alt="left" />
          </div>
        </MenuItem>
        <MenuItem sx={{ justifyContent: 'space-between' }} value="left-snake">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Snake
              <Chip size="small" label="Left" variant="outlined" />
              <Chip size="small" label="Up" variant="outlined" />
            </div>
            <img width="30px" src={leftSnake} alt="leftSnake" />
          </div>
        </MenuItem>
        <MenuItem
          sx={{ justifyContent: 'space-between' }}
          value="left-snake-flip"
        >
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Snake
              <Chip size="small" label="Left" variant="outlined" />
              <Chip size="small" label="Down" variant="outlined" />
            </div>
            <img width="30px" src={leftSnakeFlip} alt="leftSnakeFlip" />
          </div>
        </MenuItem>
        <Divider />
        <MenuItem sx={{ justifyContent: 'space-between' }} value="top">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Linear
              <Chip size="small" label="Up" variant="outlined" />
              <Chip size="small" label="Left" variant="outlined" />
            </div>
            <img width="30px" src={top} alt="top" />
          </div>
        </MenuItem>
        <MenuItem sx={{ justifyContent: 'space-between' }} value="top-flip">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Linear
              <Chip size="small" label="Up" variant="outlined" />
              <Chip size="small" label="Right" variant="outlined" />
            </div>
            <img width="30px" src={topFlip} alt="topFlip" />
          </div>
        </MenuItem>
        <MenuItem sx={{ justifyContent: 'space-between' }} value="top-snake">
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Snake
              <Chip size="small" label="Up" variant="outlined" />
              <Chip size="small" label="Left" variant="outlined" />
            </div>
            <img width="30px" src={topSnake} alt="topSnake" />
          </div>
        </MenuItem>
        <MenuItem
          sx={{ justifyContent: 'space-between' }}
          value="top-snake-flip"
        >
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              Snake
              <Chip size="small" label="Up" variant="outlined" />
              <Chip size="small" label="Right" variant="outlined" />
            </div>
            <img width="30px" src={topSnakeFlip} alt="topSnakeFlip" />
          </div>
        </MenuItem>
      </Select>
    </BladeFrame>
  )
}

export default MFillSelector
