# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/13_callback.core.ipynb (unless otherwise specified).

__all__ = ['CancelStepException', 'CancelFitException', 'CancelEpochException', 'CancelTrainException',
           'CancelValidException', 'CancelBatchException', 'event', 'Callback', 'TrainEvalCallback',
           'GatherPredsCallback', 'FetchPredsCallback']

# Cell
from ..data.all import *
from ..optimizer import *
from ..losses import BaseLoss

# Cell
#nbdev_comment _all_ = ['CancelStepException','CancelFitException','CancelEpochException','CancelTrainException','CancelValidException','CancelBatchException']

# Cell
_events = L.split('after_create before_fit before_epoch before_train before_batch after_pred after_loss \
    before_backward before_step after_cancel_step after_step after_cancel_batch after_batch after_cancel_train \
    after_train before_validate after_cancel_validate after_validate after_cancel_epoch \
    after_epoch after_cancel_fit after_fit')

mk_class('event', **_events.map_dict(),
         doc="All possible events as attributes to get tab-completion and typo-proofing")

# Cell
#nbdev_comment _all_ = ['event']

# Cell
_inner_loop = "before_batch after_pred after_loss before_backward before_step after_step after_cancel_batch after_batch".split()

# Cell
@funcs_kwargs(as_method=True)
class Callback(Stateful,GetAttr):
    "Basic class handling tweaks of the training loop by changing a `Learner` in various events"
    order,_default,learn,run,run_train,run_valid = 0,'learn',None,True,True,True
    _methods = _events

    def __init__(self, **kwargs): assert not kwargs, f'Passed unknown events: {kwargs}'
    def __repr__(self): return type(self).__name__

    def __call__(self, event_name):
        "Call `self.{event_name}` if it's defined"
        _run = (event_name not in _inner_loop or (self.run_train and getattr(self, 'training', True)) or
               (self.run_valid and not getattr(self, 'training', False)))
        res = None
        if self.run and _run: res = getattr(self, event_name, noop)()
        if event_name=='after_fit': self.run=True #Reset self.run to True at each end of fit
        return res

    def __setattr__(self, name, value):
        if hasattr(self.learn,name):
            warn(f"You are shadowing an attribute ({name}) that exists in the learner. Use `self.learn.{name}` to avoid this")
        super().__setattr__(name, value)

    @property
    def name(self):
        "Name of the `Callback`, camel-cased and with '*Callback*' removed"
        return class2attr(self, 'Callback')

# Cell
class TrainEvalCallback(Callback):
    "`Callback` that tracks the number of iterations done and properly sets training/eval mode"
    order,run_valid = -10,False
    def after_create(self): self.learn.n_epoch = 1

    def before_fit(self):
        "Set the iter and epoch counters to 0, put the model and the right device"
        self.learn.epoch,self.learn.loss = 0,tensor(0.)
        self.learn.train_iter,self.learn.pct_train = 0,0.
        device = getattr(self.dls, 'device', default_device())
        self.model.to(device)
        if isinstance(self.loss_func, (nn.Module, BaseLoss)): self.loss_func.to(device)
        if hasattr(self.model, 'reset'): self.model.reset()

    def after_batch(self):
        "Update the iter counter (in training mode)"
        self.learn.pct_train += 1./(self.n_iter*self.n_epoch)
        self.learn.train_iter += 1

    def before_train(self):
        "Set the model in training mode"
        self.learn.pct_train=self.epoch/self.n_epoch
        self.model.train()
        self.learn.training=True

    def before_validate(self):
        "Set the model in validation mode"
        self.model.eval()
        self.learn.training=False

# Cell
if not hasattr(defaults, 'callbacks'): defaults.callbacks = [TrainEvalCallback]

# Cell
_ex_docs = dict(
    CancelBatchException="Skip the rest of this batch and go to `after_batch`",
    CancelTrainException="Skip the rest of the training part of the epoch and go to `after_train`",
    CancelValidException="Skip the rest of the validation part of the epoch and go to `after_validate`",
    CancelEpochException="Skip the rest of this epoch and go to `after_epoch`",
    CancelStepException ="Skip stepping the optimizer",
    CancelFitException  ="Interrupts training and go to `after_fit`")

for c,d in _ex_docs.items(): mk_class(c,sup=Exception,doc=d)

# Cell
class GatherPredsCallback(Callback):
    "`Callback` that returns all predictions and targets, optionally `with_input` or `with_loss`"
    _stateattrs=('preds','targets','inputs','losses')
    def __init__(self,
        with_input:bool=False, # Whether to return inputs
        with_loss:bool=False, # Whether to return losses
        save_preds:Path=None, # Path to save predictions
        save_targs:Path=None, # Path to save targets
        with_preds:bool=True, # Whether to return predictions
        with_targs:bool=True, # Whether to return targets
        concat_dim:int=0, # Dimension to concatenate returned tensors
        pickle_protocol:int=2 # Pickle protocol used to save predictions and targets
    ):
        store_attr()

    def before_batch(self):
        "If `with_input`, detach batch inputs"
        if self.with_input: self.inputs.append((self.learn.to_detach(self.xb)))

    def before_validate(self):
        "Initialize containers"
        self.preds,self.targets = [],[]
        if self.with_input: self.inputs = []
        if self.with_loss:  self.losses = []

    def after_batch(self):
        "Save predictions, targets and potentially losses"
        if not hasattr(self, 'pred'): return
        preds,targs = self.learn.to_detach(self.pred),self.learn.to_detach(self.yb)
        if self.with_preds: self.preds.append(preds)
        if self.with_targs: self.targets.append(targs)
        if self.save_preds is not None:
            torch.save(preds, self.save_preds/str(self.iter), pickle_protocol=self.pickle_protocol)
        if self.save_targs is not None:
            torch.save(targs[0], self.save_targs/str(self.iter), pickle_protocol=self.pickle_protocol)
        if self.with_loss:
            bs = find_bs(self.yb)
            loss = self.loss if self.loss.numel() == bs else self.loss.view(bs,-1).mean(1)
            self.losses.append(self.learn.to_detach(loss))

    def after_validate(self):
        "Concatenate all recorded tensors"
        if not hasattr(self, 'preds'): return
        if self.with_input: self.inputs  = detuplify(to_concat(self.inputs, dim=self.concat_dim))
        if self.with_preds: self.preds   = detuplify(to_concat(self.preds, dim=self.concat_dim))
        if self.with_targs: self.targets = detuplify(to_concat(self.targets, dim=self.concat_dim))
        if self.with_loss:  self.losses  = to_concat(self.losses)

    def all_tensors(self):
        "Returns all recorded tensors in the order (inputs, preds, targets, losses)"
        res = [self.preds if self.with_preds else None, self.targets if self.with_targs else None]
        if self.with_input: res = [self.inputs] + res
        if self.with_loss:  res.append(self.losses)
        return res

# Cell
class FetchPredsCallback(Callback):
    "A callback to fetch predictions during the training loop"
    remove_on_fetch = True
    def __init__(self,
        ds_idx:int=1, # Index of databunchset in fetching `Learner` predictions if `dl` is not present
        dl:DataLoader=None, # `DataLoader` in fetching `Learner` predictions
        with_input:bool=False, # Whether to return inputs in `GatherPredsCallback`
        with_decoded:bool=False, # Whether to return decoded predictions from `decodes` method of `Learner` loss function
        cbs:list=None, # `Callback` list for the `Learner`
        reorder:bool=True # Whether to sort prediction results
    ):
        self.cbs = L(cbs)
        store_attr('ds_idx,dl,with_input,with_decoded,reorder')

    def after_validate(self):
        "Fetch predictions from `Learner`"
        to_rm = L(cb for cb in self.learn.cbs if getattr(cb, 'remove_on_fetch', False))
        with self.learn.removed_cbs(to_rm + self.cbs) as learn:
            self.preds = learn.get_preds(ds_idx=self.ds_idx, dl=self.dl,
                with_input=self.with_input, with_decoded=self.with_decoded, inner=True, reorder=self.reorder)