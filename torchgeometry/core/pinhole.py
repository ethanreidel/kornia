from typing import Iterable
import warnings

import torch
import torch.nn as nn

from .conversions import rtvec_to_pose
from .transformations import inverse_pose


__all__ = [
    "PinholeCamera",
    "PinholeCamerasList",
    # functional api
    "pinhole_matrix",
    "inverse_pinhole_matrix",
    "scale_pinhole",
    "homography_i_H_ref",
    # layer api
    "PinholeMatrix",
    "InversePinholeMatrix",
]


class PinholeCamera:
    r"""Class that represents a Pinhole Camera model.

    Args:
        intrinsics (torch.Tensor): tensor with shape :math:`(B, 4, 4)`
          containing the full 4x4 camera calibration matrix.
        extrinsics (torch.Tensor): tensor with shape :math:`(B, 4, 4)`
          containing the full 4x4 rotation-translation matrix.
        height (torch.Tensor): tensor with shape :math:`(B)` containing the
          image height.
        widht (torch.Tensor): tensor with shape :math:`(B)` containing the image
          width.

    .. note::
        We assume that class attributes are batched in order to take advantage
          of PyTorch parallelism.
    """

    def __init__(self, intrinsics: torch.Tensor,
                 extrinsics: torch.Tensor,
                 height: torch.Tensor,
                 width: torch.Tensor) -> None:
        # verify batch size and shapes
        self._check_valid([intrinsics, extrinsics, height, width])
        self._check_valid_params(intrinsics, "intrinsics")
        self._check_valid_params(extrinsics, "extrinsics")
        self._check_valid_shape(height, "height")
        self._check_valid_shape(width, "width")
        # set class attributes
        self.height: torch.Tensor = height
        self.width: torch.Tensor = width
        self._intrinsics: torch.Tensor = intrinsics
        self._extrinsics: torch.Tensor = extrinsics

    @staticmethod
    def _check_valid(data_iter: Iterable[torch.Tensor]) -> bool:
        if not all(data.shape[0] for data in data_iter):
            raise ValueError("Arguments shapes must match")
        return True

    @staticmethod
    def _check_valid_params(
            data: torch.Tensor,
            data_name: str) -> torch.Tensor:
        if len(data.shape) not in (3, 4,) and data.shape[-2:] is not (4, 4):
            raise ValueError("Argument {0} shape must be in the following shape"
                             " Bx4x4 or BxNx4x4. Got {1}".format(data_name,
                                                                 data.shape))
        return True

    @staticmethod
    def _check_valid_shape(
            data: torch.Tensor,
            data_name: str) -> torch.Tensor:
        if not len(data.shape) == 1:
            raise ValueError("Argument {0} shape must be in the following shape"
                             " B. Got {1}".format(data_name, data.shape))
        return True

    @property
    def intrinsics(self) -> torch.Tensor:
        r"""The full 4x4 intrinsics matrix.

        Returns:
            torch.Tensor: tensor of shape :math:`(B, 4, 4)`
        """
        assert self._check_valid_params(self._intrinsics, "intrinsics")
        return self._intrinsics

    @property
    def extrinsics(self) -> torch.Tensor:
        r"""The full 4x4 extrinsics matrix.

        Returns:
            torch.Tensor: tensor of shape :math:`(B, 4, 4)`
        """
        assert self._check_valid_params(self._extrinsics, "extrinsics")
        return self._extrinsics

    @property
    def batch_size(self) -> int:
        r"""Returns the batch size of the storage.

        Returns:
            int: batch size value
        """
        return self.intrinsics.shape[0]

    @property
    def fx(self) -> torch.Tensor:
        r"""Returns the focal lenght in the x-direction.

        Returns:
            torch.Tensor: tensor of shape :math:`(B)`
        """
        return self.intrinsics[..., 0, 0]

    @property
    def fy(self) -> torch.Tensor:
        r"""Returns the focal lenght in the y-direction.

        Returns:
            torch.Tensor: tensor of shape :math:`(B)`
        """
        return self.intrinsics[..., 1, 1]

    @property
    def cx(self) -> torch.Tensor:
        r"""Returns the x-coordinate of the principal point.

        Returns:
            torch.Tensor: tensor of shape :math:`(B)`
        """
        return self.intrinsics[..., 0, 2]

    @property
    def cy(self) -> torch.Tensor:
        r"""Returns the y-coordinate of the principal point.

        Returns:
            torch.Tensor: tensor of shape :math:`(B)`
        """
        return self.intrinsics[..., 1, 2]

    @property
    def tx(self) -> torch.Tensor:
        r"""Returns the x-coordinate of the translation vector.

        Returns:
            torch.Tensor: tensor of shape :math:`(B)`
        """
        return self.extrinsics[..., 0, -1]

    @tx.setter
    def tx(self, value) -> 'PinholeCamera':
        r"""Set the x-coordinate of the translation vector with the given
        value.
        """
        self.extrinsics[..., 0, -1] = value
        return self

    @property
    def ty(self) -> torch.Tensor:
        r"""Returns the y-coordinate of the translation vector.

        Returns:
            torch.Tensor: tensor of shape :math:`(B)`
        """
        return self.extrinsics[..., 1, -1]

    @ty.setter
    def ty(self, value) -> 'PinholeCamera':
        r"""Set the y-coordinate of the translation vector with the given
        value.
        """
        self.extrinsics[..., 1, -1] = value
        return self

    @property
    def tz(self) -> torch.Tensor:
        r"""Returns the z-coordinate of the translation vector.

        Returns:
            torch.Tensor: tensor of shape :math:`(B)`
        """
        return self.extrinsics[..., 2, -1]

    @tz.setter
    def tz(self, value) -> 'PinholeCamera':
        r"""Set the y-coordinate of the translation vector with the given
        value.
        """
        self.extrinsics[..., 2, -1] = value
        return self

    @property
    def rt_matrix(self) -> torch.Tensor:
        r"""Returns the 3x4 rotation-translation matrix.

        Returns:
            torch.Tensor: tensor of shape :math:`(B, 3, 4)`
        """
        return self.extrinsics[..., :3, :4]

    @property
    def camera_matrix(self) -> torch.Tensor:
        r"""Returns the 3x3 camera matrix containing the intrinsics.

        Returns:
            torch.Tensor: tensor of shape :math:`(B, 3, 3)`
        """
        return self.intrinsics[..., :3, :3]

    @property
    def rotation_matrix(self) -> torch.Tensor:
        r"""Returns the 3x3 rotation matrix from the extrinsics.

        Returns:
            torch.Tensor: tensor of shape :math:`(B, 3, 3)`
        """
        return self.extrinsics[..., :3, :3]

    @property
    def translation_vector(self) -> torch.Tensor:
        r"""Returns the translation vector from the extrinsics.

        Returns:
            torch.Tensor: tensor of shape :math:`(B, 3, 1)`
        """
        return self.extrinsics[..., :3, -1:]

    def clone(self) -> 'PinholeCamera':
        r"""Returns a deep copy of the current object instance."""
        height: torch.Tensor = self.height.clone()
        width: torch.Tensor = self.width.clone()
        intrinsics: torch.Tensor = self.intrinsics.clone()
        extrinsics: torch.Tensor = self.extrinsics.clone()
        return PinholeCamera(intrinsics, extrinsics, height, width)

    def intrinsics_inverse(self) -> torch.Tensor:
        r"""Returns the inverse of the 4x4 instrisics matrix.

        Returns:
            torch.Tensor: tensor of shape :math:`(B, 4, 4)`
        """
        return self.intrinsics.inverse()

    def scale(self, scale_factor) -> 'PinholeCamera':
        r"""Scales the pinhole model.

        Args:
            scale_factor (torch.Tensor): a tensor with the scale factor. It has
              to be broadcastable with class members. The expected shape is
              :math:`(B)` or :math:`(1)`.

        Returns:
            PinholeCamera: the camera model with scaled parameters.
        """
        # scale the intrinsic parameters
        intrinsics: torch.Tensor = self.intrinsics.clone()
        intrinsics[..., 0, 0] *= scale_factor
        intrinsics[..., 1, 1] *= scale_factor
        intrinsics[..., 0, 2] *= scale_factor
        intrinsics[..., 1, 2] *= scale_factor
        # scale the image height/width
        height: torch.Tensor = scale_factor * self.height.clone()
        width: torch.Tensor = scale_factor * self.width.clone()
        return PinholeCamera(intrinsics, self.extrinsics, height, width)

    def scale_(self, scale_factor) -> 'PinholeCamera':
        r"""Scales the pinhole model in-place.

        Args:
            scale_factor (torch.Tensor): a tensor with the scale factor. It has
              to be broadcastable with class members. The expected shape is
              :math:`(B)` or :math:`(1)`.

        Returns:
            PinholeCamera: the camera model with scaled parameters.
        """
        # scale the intrinsic parameters
        self.intrinsics[..., 0, 0] *= scale_factor
        self.intrinsics[..., 1, 1] *= scale_factor
        self.intrinsics[..., 0, 2] *= scale_factor
        self.intrinsics[..., 1, 2] *= scale_factor
        # scale the image height/width
        self.height *= scale_factor
        self.width *= scale_factor
        return self

    # NOTE: just for test. Decide if we keep it.
    @classmethod
    def from_parameters(
            self,
            fx,
            fy,
            cx,
            cy,
            height,
            width,
            tx,
            ty,
            tz,
            batch_size=1):
        # create the camera matrix
        intrinsics = torch.zeros(batch_size, 4, 4)
        intrinsics[..., 0, 0] += fx
        intrinsics[..., 1, 1] += fy
        intrinsics[..., 0, 2] += cx
        intrinsics[..., 1, 2] += cy
        intrinsics[..., 2, 2] += 1.0
        intrinsics[..., 3, 3] += 1.0
        # create the pose matrix
        extrinsics = torch.eye(4).repeat(batch_size, 1, 1)
        extrinsics[..., 0, -1] += tx
        extrinsics[..., 1, -1] += ty
        extrinsics[..., 2, -1] += tz
        # create image hegith and width
        height_tmp = torch.zeros(batch_size)
        height_tmp[..., 0] += height
        width_tmp = torch.zeros(batch_size)
        width_tmp[..., 0] += width
        return self(intrinsics, extrinsics, height_tmp, width_tmp)


class PinholeCamerasList(PinholeCamera):
    r"""Class that represents a list of pinhole cameras.

    The class inherits from :class:`~torchgeometry.PinholeCamera` meaning that
    it will keep the same class properties but with an extra dimension.

    .. note::
        The underlying data tensor will be stacked in the first dimension.
        That's it, given a list of two camera instances, the intrinsics tensor
        will have a shape :math:`(B, N, 4, 4)` where :math:`B` is the batch
        size and :math:`N` is the numbers of cameras (in this case two).

    Args:
        pinholes_list (Iterable[PinholeCamera]): a python tuple or list
          containg a set of `PinholeCamera` instances.
    """

    def __init__(self, pinholes_list: Iterable[PinholeCamera]) -> None:
        self._initialize_parameters(pinholes_list)

    def _initialize_parameters(
            self,
            pinholes: Iterable[PinholeCamera]) -> 'PinholeCamerasList':
        r"""Initialises the class attributes given a cameras list."""
        if not isinstance(pinholes, (list, tuple,)):
            raise TypeError("pinhole must of type list or tuple. Got {}"
                            .format(type(pinholes)))
        height, width = [], []
        intrinsics, extrinsics = [], []
        for pinhole in pinholes:
            if not isinstance(pinhole, PinholeCamera):
                raise TypeError("Argument pinhole must be from type "
                                "PinholeCamera. Got {}".format(type(pinhole)))
            height.append(pinhole.height)
            width.append(pinhole.width)
            intrinsics.append(pinhole.intrinsics)
            extrinsics.append(pinhole.extrinsics)
        # contatenate and set members. We will assume BxNx4x4
        self.height: torch.Tensor = torch.stack(height, dim=1)
        self.width: torch.Tensor = torch.stack(width, dim=1)
        self._intrinsics: torch.Tensor = torch.stack(intrinsics, dim=1)
        self._extrinsics: torch.Tensor = torch.stack(extrinsics, dim=1)
        return self

    @property
    def num_cameras(self) -> int:
        r"""Returns the number of pinholes cameras per batch."""
        num_cameras: int = -1
        if self.intrinsics is not None:
            num_cameras = int(self.intrinsics.shape[1])
        return num_cameras

    def get_pinhole(self, idx: int) -> PinholeCamera:
        r"""Returns a PinholeCamera object with parameters such as Bx4x4."""
        height: torch.Tensor = self.height[..., idx]
        width: torch.Tensor = self.width[..., idx]
        intrinsics: torch.Tensor = self.intrinsics[:, idx]
        extrinsics: torch.Tensor = self.extrinsics[:, idx]
        return PinholeCamera(intrinsics, extrinsics, height, width)


def pinhole_matrix(pinholes, eps=1e-6):
    r"""Function that returns the pinhole matrix from a pinhole model

    Args:
        pinholes (Tensor): tensor of pinhole models.

    Returns:
        Tensor: tensor of pinhole matrices.

    Shape:
        - Input: :math:`(N, 12)`
        - Output: :math:`(N, 4, 4)`

    Example:
        >>> pinhole = torch.rand(1, 12)    # Nx12
        >>> pinhole_matrix = tgm.pinhole_matrix(pinhole)  # Nx4x4
    """
    warnings.warn("pinhole_matrix will be deprecated in version 0.2, "
                  "use PinholeCamera.camera_matrix instead",
                  PendingDeprecationWarning)
    assert len(pinholes.shape) == 2 and pinholes.shape[1] == 12, pinholes.shape
    # unpack pinhole values
    fx, fy, cx, cy = torch.chunk(pinholes[..., :4], 4, dim=1)  # Nx1
    # create output container
    k = torch.eye(4, device=pinholes.device, dtype=pinholes.dtype) + eps
    k = k.view(1, 4, 4).repeat(pinholes.shape[0], 1, 1)  # Nx4x4
    # fill output with pinhole values
    k[..., 0, 0:1] = fx
    k[..., 0, 2:3] = cx
    k[..., 1, 1:2] = fy
    k[..., 1, 2:3] = cy
    return k


def inverse_pinhole_matrix(pinhole, eps=1e-6):
    r"""Returns the inverted pinhole matrix from a pinhole model

    Args:
        pinholes (Tensor): tensor with pinhole models.

    Returns:
        Tensor: tensor of inverted pinhole matrices.

    Shape:
        - Input: :math:`(N, 12)`
        - Output: :math:`(N, 4, 4)`

    Example:
        >>> pinhole = torch.rand(1, 12)    # Nx12
        >>> pinhole_matrix_inv = tgm.inverse_pinhole_matrix(pinhole)  # Nx4x4
    """
    warnings.warn("inverse_pinhole_matrix will be deprecated in version 0.2, "
                  "use PinholeCamera.camera_matrix() instead",
                  PendingDeprecationWarning)
    assert len(pinhole.shape) == 2 and pinhole.shape[1] == 12, pinhole.shape
    # unpack pinhole values
    fx, fy, cx, cy = torch.chunk(pinhole[..., :4], 4, dim=1)  # Nx1
    # create output container
    k = torch.eye(4, device=pinhole.device, dtype=pinhole.dtype)
    k = k.view(1, 4, 4).repeat(pinhole.shape[0], 1, 1)  # Nx4x4
    # fill output with inverse values
    k[..., 0, 0:1] = 1. / (fx + eps)
    k[..., 1, 1:2] = 1. / (fy + eps)
    k[..., 0, 2:3] = -1. * cx / (fx + eps)
    k[..., 1, 2:3] = -1. * cy / (fy + eps)
    return k


def scale_pinhole(pinholes, scale):
    r"""Scales the pinhole matrix for each pinhole model.

    Args:
        pinholes (Tensor): tensor with the pinhole model.
        scale (Tensor): tensor of scales.

    Returns:
        Tensor: tensor of scaled pinholes.

    Shape:
        - Input: :math:`(N, 12)` and :math:`(N, 1)`
        - Output: :math:`(N, 12)`

    Example:
        >>> pinhole_i = torch.rand(1, 12)  # Nx12
        >>> scales = 2.0 * torch.ones(1)   # N
        >>> pinhole_i_scaled = tgm.scale_pinhole(pinhole_i)  # Nx12
    """
    warnings.warn("scale_pinhole will be deprecated in version 0.2, "
                  "use PinholeCamera.scale() instead",
                  PendingDeprecationWarning)
    assert len(pinholes.shape) == 2 and pinholes.shape[1] == 12, pinholes.shape
    assert len(scale.shape) == 1, scale.shape
    pinholes_scaled = pinholes.clone()
    pinholes_scaled[..., :6] = pinholes[..., :6] * scale.unsqueeze(-1)
    return pinholes_scaled


def get_optical_pose_base(pinholes):
    """Get extrinsic transformation matrices for pinholes

    Args:
        pinholes (Tensor): tensor of form [fx fy cx cy h w rx ry rz tx ty tz]
                           of size (N, 12).

    Returns:
        Tensor: tensor of extrinsic transformation matrices of size (N, 4, 4).

    """
    assert len(pinholes.shape) == 2 and pinholes.shape[1] == 12, pinholes.shape
    optical_pose_parent = pinholes[..., 6:]
    return rtvec_to_pose(optical_pose_parent)


def homography_i_H_ref(pinhole_i, pinhole_ref):
    r"""Homography from reference to ith pinhole

    .. math::

        H_{ref}^{i} = K_{i} * T_{ref}^{i} * K_{ref}^{-1}

    Args:
        pinhole_i (Tensor): tensor with pinhole model for ith frame.
        pinhole_ref (Tensor): tensor with pinhole model for reference frame.

    Returns:
        Tensor: tensors that convert depth points (u, v, d) from
        pinhole_ref to pinhole_i.

    Shape:
        - Input: :math:`(N, 12)` and :math:`(N, 12)`
        - Output: :math:`(N, 4, 4)`

    Example:
        >>> pinhole_i = torch.rand(1, 12)    # Nx12
        >>> pinhole_ref = torch.rand(1, 12)  # Nx12
        >>> i_H_ref = tgm.homography_i_H_ref(pinhole_i, pinhole_ref)  # Nx4x4
    """
    assert len(
        pinhole_i.shape) == 2 and pinhole_i.shape[1] == 12, pinhole.shape
    assert pinhole_i.shape == pinhole_ref.shape, pinhole_ref.shape
    i_pose_base = get_optical_pose_base(pinhole_i)
    ref_pose_base = get_optical_pose_base(pinhole_ref)
    i_pose_ref = torch.matmul(i_pose_base, inverse_pose(ref_pose_base))
    return torch.matmul(
        pinhole_matrix(pinhole_i),
        torch.matmul(i_pose_ref, inverse_pinhole_matrix(pinhole_ref)))


# layer api


class PinholeMatrix(nn.Module):
    r"""Creates an object that returns the pinhole matrix from a pinhole model

    Args:
        pinholes (Tensor): tensor of pinhole models.

    Returns:
        Tensor: tensor of pinhole matrices.

    Shape:
        - Input: :math:`(N, 12)`
        - Output: :math:`(N, 4, 4)`

    Example:
        >>> pinhole = torch.rand(1, 12)          # Nx12
        >>> transform = tgm.PinholeMatrix()
        >>> pinhole_matrix = transform(pinhole)  # Nx4x4
    """

    def __init__(self):
        super(PinholeMatrix, self).__init__()

    def forward(self, input):
        return pinhole_matrix(input)


class InversePinholeMatrix(nn.Module):
    r"""Returns and object that inverts a pinhole matrix from a pinhole model

    Args:
        pinholes (Tensor): tensor with pinhole models.

    Returns:
        Tensor: tensor of inverted pinhole matrices.

    Shape:
        - Input: :math:`(N, 12)`
        - Output: :math:`(N, 4, 4)`

    Example:
        >>> pinhole = torch.rand(1, 12)              # Nx12
        >>> transform = tgm.InversePinholeMatrix()
        >>> pinhole_matrix_inv = transform(pinhole)  # Nx4x4
    """

    def __init__(self):
        super(InversePinholeMatrix, self).__init__()

    def forward(self, input):
        return inverse_pinhole_matrix(input)
