export type IDir =
  | 'right'
  | 'right-snake'
  | 'right-flip'
  | 'right-snake-flip'
  | 'left'
  | 'left-snake'
  | 'left-flip'
  | 'left-snake-flip'
  | 'top'
  | 'top-snake'
  | 'top-flip'
  | 'top-snake-flip'
  | 'bottom'
  | 'bottom-snake'
  | 'bottom-flip'
  | 'bottom-snake-flip'

export type IMCell = {
  deviceId: string
  pixel: number
}

export const MCell: IMCell = { deviceId: '', pixel: 0 }

/**
 * Calculates the maximum available pixel given the input data
 */
export const getMaxRange = (
  direction: IDir,
  row: number,
  col: number,
  rowN: number,
  colN: number
) => {
  let maxRange = 0
  if (direction.includes('right')) {
    maxRange = colN * rowN - (row * colN + col)
    if (direction.includes('flip')) {
      maxRange = row * colN + colN - col
    }
  } else if (direction.includes('left')) {
    maxRange = row * colN + col + 1
    if (direction.includes('flip')) {
      maxRange = (rowN - row - 1) * colN + col + 1
    }
  } else if (direction.includes('bottom')) {
    maxRange = colN * rowN - (rowN * col + (rowN - row - 1))
    if (direction.includes('flip')) {
      maxRange = rowN * col + (rowN - row)
    }
  } else if (direction.includes('top')) {
    maxRange = rowN * col + row + 1
    if (direction.includes('flip')) {
      maxRange = colN * rowN - (rowN * col + (rowN - row - 1))
    }
  }
  return maxRange
}

/**
 * deep clone
 */
export const clone = (input: any) => JSON.parse(JSON.stringify(input))
