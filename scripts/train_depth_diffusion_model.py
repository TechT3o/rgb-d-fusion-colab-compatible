import argparse


parser = argparse.ArgumentParser(description="Train image conditioned depth diffusion model")
parser.add_argument("-t","--time_steps", type=int, default=600, help="Number of timesteps used in the forward and reverse denoising process")
parser.add_argument("-s","--sampling_steps", type=int, default=600, help="Number of steps used for sampling")
parser.add_argument("-e","--epochs", type=int, default=100, help="Number of epochs the model is trained")
parser.add_argument("-b","--batch_size", type=int, default=16, help="Number of samples that are put throught the model simultaniously. The bigger the more memory is required by the GPU.")
parser.add_argument("-cr","--crop_width_half", action="store_true", help="Center crops the dataset to obtain sample with half the width.")
parser.add_argument("-ma", "--model_architecture", choices=["unet","unet3+"],default="unet3+", help="Model base architecture. Must match the architecture used during training.")
parser.add_argument("-mb","--model_basedim", type=int, default=64, help="Number of channels in the base layer.")
parser.add_argument("-mm","--model_dim_multiplier", default= (1, 2, 4, 8), nargs='+', type=int, help="A list of integers where each element represent the multiplier applied to model_basedim to create a layer in the unet architecture.")
parser.add_argument("-nb","--model_num_blocks", default= (1, 1, 1, 1), nargs='+', type=int, help="A list of integers where each element represent the number of blocks created in a stage of the UNet Model, where Block(x) = Attention(ResBlock(x)).")
parser.add_argument("-at","--model_attention_blocks", default= (1, 1, 1, 1), nargs='+', type=int, help="A list of integers where each element represent a bool wheathor o r not a linear attention block is used at the given UNet stage. 1= true, 0=false.")
parser.add_argument("-nr","--model_num_res_blocks", default= (2, 2, 2, 2), nargs='+', type=int, help="A list of integers where each element represent the number of ResBlocks created within a Block in a stage of the UNet Model, where each Resblock contains 'numResBlocks' consecutive resBlocks.")
parser.add_argument("-dr","--drop_res_block_rate", default= (0.0, 0.0, 0.0, 0.0), nargs='+', type=float, help="A list of integers where each element represent the probability of dropping a ResBlocks within a Block in a stage of the UNet Model.")
parser.add_argument("-l", "--loss_weighting", choices=["P2","simple"],default="P2", help="Select if the calculated loss should be weighted depending on the timestep.")
parser.add_argument("-d", "--dataset", default="v_human_rendered", choices=["v_human_rendered","24k_358seg_equalised","19k_316seg_equalised"], help="The dataset used for evaluation")
parser.add_argument("-hw","--height_width", default= (64,64), nargs='+', type=int, help="Spatial resolution of the input data")
parser.add_argument("-nt","--number_samples_train", type=int, default=None, help="Number of samples to load from train set. If None, all samples are read.")
parser.add_argument("-nv","--number_samples_test", type=int, default=None, help="Number of samples to load from train set. If None, all samples are read.")
parser.add_argument("-v", "--variance", default="upper_bound", choices=["lower_bound","upper_bound","learned","learned_range"], help="A diffusion model samples from distributiones diffened by their mean and their variance. The variance can either be set to a constant value or can be learned.")
parser.add_argument("-bs", "--beta_schedule", default="cosine", choices=["cosine","linear","sigmoid"], help="Function used for the diffusion process.")
parser.add_argument("-a","--xla_accelerate",action="store_true", help="Whether or not to accelerate using XLA for algebraic computations")
parser.add_argument("-m","--mixed_precission",action="store_true", help="Whether or not to use mixed precission")
parser.add_argument("-c","--checkpoint_path_to_restore", default=None, help="Path to the checkpoint that should be restored.")
parser.add_argument("-fs","--sample_frequency", type=int, default=50, help="Number of epochs after which the model is sampled during training")
parser.add_argument("-ft","--test_frequency", type=int, default=5, help="Number of epochs after which a test step is performed during training")
parser.add_argument("-fc","--checkpoint_period", type=int, default=50, help="Number of epochs after which a checkpoint is stored during training")
parser.add_argument("-op", "--optimizer", choices=["adam","adamW","yogi","sgd","sgdW"],default="adam", help="Optimizer used to optimize the model.")
parser.add_argument("-ld", "--learning_rate_decay", choices=["linear","cosine","cosine_restart","step","exponential"],default=None, help="Learning rate decay.")
parser.add_argument("-wu","--warm_up_epochs", type=int, default=0, help="Number of warm up epochs where the learning rate is linearly increasing until the set learning rate")
parser.add_argument("-ad","--weight_decay", type=float, help="Weight decay rate used together with AdamW or SDGW Optimizer")
parser.add_argument("-ds", "--down_sampling", choices=["max","average","conv"],default="conv", help="Method to downsample a feature map in the encoder.")
parser.add_argument("-od","--outdir_name", default=None, help="Provide a name to the output directory. can be used to schedule multiple runs and eval runs")
parser.add_argument("-lr","--learning_rate", type=float, default=None, help="Learning rate for the optimization process")

parser.add_argument("-afl","--apply_flip",action="store_true", help="Whether or not to apply flip augmentation")
parser.add_argument("-asc","--apply_scale",action="store_true", help="Whether or not to apply scale augmentation")
parser.add_argument("-ash","--apply_shift",action="store_true", help="Whether or not to apply shift augmentation")
parser.add_argument("-arb","--apply_rgb_blur",action="store_true", help="Whether or not to apply rgb blur augmentation")
parser.add_argument("-adb","--apply_depth_blur",action="store_true", help="Whether or not to apply depth blur augmentation")

parser.add_argument("-bd","--base_dir", default="/tf", help="Base directory for saving output directories and loading datasets from")

args = parser.parse_args()

import logging


logging.basicConfig(level="INFO", format="[%(levelname)s | %(asctime)s] - %(message)s", datefmt="%I:%M:%S %p")
logging.info("---------------------------------------------------------")
logging.info(f"Running {__file__} ")
logging.info("---------------------------------------------------------")
logging.debug(args)

import os


os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # Only print errors, not warnings or infos
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"  # Enable EXR

import sys


# Get the parent directory to be able to import the files located in imports
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

import subprocess
import time

import tensorflow as tf

import DeepSaki
import imports.dataset as cdd_dataset
import imports.helper as cdd_helper
import imports.model as cdd_model
import tensorflow_addons as tfa
import yaml


result = subprocess.run(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
currentCommit = result.stdout.decode("utf-8").strip()

CONFIG = {
    "MODEL": args.model_architecture,
    "BASE_DIM": args.model_basedim,
    "DIM_MULTIPLIER": args.model_dim_multiplier,
    "NUM_BLOCKS": args.model_num_blocks,
    "ATTENTION_BLOCKS": args.model_attention_blocks,
    "NUM_RES_BLOCKS": args.model_num_res_blocks,
    "DROP_RESBLOCK_RATE": args.drop_res_block_rate,
    "TIMESTEPS": args.time_steps,
    "SAMPLING_STEPS": args.sampling_steps,
    "VARIANCE_TYPE": args.variance,
    "LAMBDA_L_VLB": 0.001,
    "LOSS_WEIGHTING_TYPE": args.loss_weighting,
    "BETA_SCHEDULE": args.beta_schedule,
    "EPOCHS": args.epochs,
    "OPTIMIZER": args.optimizer,
    "DATASET": args.dataset,
    "IMG_HEIGHT_WIDTH": args.height_width,
    "NUMBER_SAMPLES_TRAIN": args.number_samples_train,
    "NUMBER_SAMPLES_TEST": args.number_samples_test,
    "BATCH_SIZE_PER_REPLICA": args.batch_size,
    "USE_XLA_ACCELERATE": args.xla_accelerate,
    "USE_MIXED_PRECISION": args.mixed_precission,
    "RESTORE_CHECKPOINT": bool(args.checkpoint_path_to_restore),
    "CHECKPOINT_PATH_TO_RESTORE": args.checkpoint_path_to_restore,
    "CHECKPOINT_FREQUENCY": args.checkpoint_period,
    "GIT_COMMIT": currentCommit,
    "CROP_WIDTH_HALF": args.crop_width_half,
    "SAMPLE_FREQUENCY": args.sample_frequency,
    "TEST_FREQUENCY": args.test_frequency,
    "LR_DECAY": args.learning_rate_decay,
    "WARM_UP_EPOCHS": args.warm_up_epochs,
    "DOWN_SAMPLING": args.down_sampling,
    "CONDITION_FORMAT": "rgb",
    "DIFFUSION_FORMAT": "depth",
    "APPLY_FLIP": args.apply_flip,
    "APPLY_SCALE": args.apply_scale,
    "APPLY_SHIFT": args.apply_shift,
    "APPLY_RGB_BLUR": args.apply_rgb_blur,
    "APPLY_DEPTH_BLUR": args.apply_depth_blur,
}
CONFIG["SCOPE"] = "depth_diffusion"

if CONFIG["CROP_WIDTH_HALF"]:
    CONFIG["IMG_HEIGHT_WIDTH"] = (CONFIG["IMG_HEIGHT_WIDTH"][0], int(CONFIG["IMG_HEIGHT_WIDTH"][1] / 2))

if args.learning_rate:
    CONFIG["LEARNING_RATE"] = args.learning_rate
else:
    # following improved diffusion model approach
    if CONFIG["BASE_DIM"] == 64:
        CONFIG["LEARNING_RATE"] = 2e-5
    elif CONFIG["BASE_DIM"] == 96:
        CONFIG["LEARNING_RATE"] = 6e-5
    elif CONFIG["BASE_DIM"] == 128:
        CONFIG["LEARNING_RATE"] = 1e-4
    else:
        CONFIG["LEARNING_RATE"] = 1e-4
    if CONFIG["OPTIMIZER"] == "yogi":
        CONFIG["LEARNING_RATE"] = (
            5 * CONFIG["LEARNING_RATE"]
        )  # acc. to yogi paper learningrate is 5-10 times higher as for adam

# according to AdamW paper 0.025 or 0.05 seem to work good, which was not the case for me.
# Inspired by https://www.tensorflow.org/api_docs/python/tf/keras/optimizers/AdamW I set it to be 4*learning rate, if not explicitly provided.
if args.weight_decay:
    CONFIG["WEIGHT_DECAY"] = args.weight_decay
else:
    CONFIG["WEIGHT_DECAY"] = 4 * CONFIG["LEARNING_RATE"]

# set random seed
RANDOM_SEED = 1911
tf.random.set_seed(RANDOM_SEED)

strategy, CONFIG["RUNTIME_ENVIRONMENT"], hw_accelerator_handle = DeepSaki.utils.DetectHw()
CONFIG["GLOBAL_BATCH_SIZE"] = CONFIG["BATCH_SIZE_PER_REPLICA"] * strategy.num_replicas_in_sync
CONFIG["DISTRIBUTED_TRAINING"] = isinstance(strategy, tf.distribute.MirroredStrategy)

if CONFIG["USE_MIXED_PRECISION"]:
    DeepSaki.utils.EnableMixedPrecision()

if CONFIG["USE_XLA_ACCELERATE"]:
    DeepSaki.utils.EnableXlaAcceleration()

os.chdir(args.base_dir)
if args.outdir_name:
    CONFIG["OUTDIR"] = f"output_runs/DepthDiffusion/{args.outdir_name}"
else:
    CONFIG["OUTDIR"] = "output_runs/DepthDiffusion/{timestamp}".format(timestamp=int(time.time()))
path1 = os.path.join(CONFIG["OUTDIR"], "checkpoints")
path2 = os.path.join(CONFIG["OUTDIR"], "illustrations")
subprocess.run(["mkdir", "-p", path1])
subprocess.run(["mkdir", "-p", path2])

with open(os.path.join(CONFIG["OUTDIR"], "CONFIG.yml"), "w") as outfile:
    yaml.dump(CONFIG, outfile)

#############################################################
###### Dataset
#############################################################
policy = tf.keras.mixed_precision.global_policy()

trainDirectory = f'manual_datasets/{CONFIG["DATASET"]}/train'
testDirectory = f'manual_datasets/{CONFIG["DATASET"]}/test'

train_ds = cdd_dataset.GetDatasetDepthDiffusionStreamed(
    datasetDirectory=trainDirectory,
    batchSize=CONFIG["GLOBAL_BATCH_SIZE"],
    img_height_width=CONFIG["IMG_HEIGHT_WIDTH"],
    NumberOfSamplesToRead=CONFIG["NUMBER_SAMPLES_TRAIN"],
    dtype=policy.variable_dtype,
    drop_remainder=True,
    cropWidthHalf=CONFIG["CROP_WIDTH_HALF"],
    shuffle=True,
    apply_flip=CONFIG["APPLY_FLIP"],
    apply_scale=CONFIG["APPLY_SCALE"],
    apply_shift=CONFIG["APPLY_SHIFT"],
    apply_rgb_blur=CONFIG["APPLY_RGB_BLUR"],
    apply_depth_blur=CONFIG["APPLY_DEPTH_BLUR"],
)

test_ds = cdd_dataset.GetDatasetDepthDiffusionStreamed(
    datasetDirectory=testDirectory,
    batchSize=CONFIG["GLOBAL_BATCH_SIZE"],
    img_height_width=CONFIG["IMG_HEIGHT_WIDTH"],
    NumberOfSamplesToRead=CONFIG["NUMBER_SAMPLES_TEST"],
    dtype=policy.variable_dtype,
    drop_remainder=True,
    cropWidthHalf=CONFIG["CROP_WIDTH_HALF"],
    shuffle=False,
    apply_flip=False,
    apply_scale=False,
    apply_shift=False,
    apply_rgb_blur=False,
    apply_depth_blur=False,
)

#############################################################
###### Training Preparation
#############################################################
if CONFIG["OPTIMIZER"] == "adam":
    optimizer = tf.keras.optimizers.Adam(learning_rate=CONFIG["LEARNING_RATE"])
elif CONFIG["OPTIMIZER"] == "adamW":
    optimizer = tfa.optimizers.AdamW(weight_decay=CONFIG["WEIGHT_DECAY"], learning_rate=CONFIG["LEARNING_RATE"])
elif CONFIG["OPTIMIZER"] == "sgd":
    optimizer = tf.keras.optimizers.SGD(learning_rate=CONFIG["LEARNING_RATE"], momentum=0.9)
elif CONFIG["OPTIMIZER"] == "sgdW":
    optimizer = tfa.optimizers.SGDW(
        weight_decay=CONFIG["WEIGHT_DECAY"], learning_rate=CONFIG["LEARNING_RATE"], momentum=0.9
    )
elif CONFIG["OPTIMIZER"] == "yogi":
    optimizer = tfa.optimizers.Yogi(learning_rate=CONFIG["LEARNING_RATE"])
else:
    raise Exception(f'Undefined optimizer provided: {CONFIG["OPTIMIZER"]}')

with strategy.scope():
    if CONFIG["MODEL"] == "unet":
        model = cdd_model.ConditionalUnet(
            baseDim=CONFIG["BASE_DIM"],
            dim_mults=CONFIG["DIM_MULTIPLIER"],
            numBlocks=CONFIG["NUM_BLOCKS"],
            numResBlocks=CONFIG["NUM_RES_BLOCKS"],
            attentionBlocks=CONFIG["ATTENTION_BLOCKS"],
            dropResBlockRate=CONFIG["DROP_RESBLOCK_RATE"],
            diffusionChannels=cdd_helper.get_channels_from_format(CONFIG["DIFFUSION_FORMAT"]),
            learned_variance=CONFIG["VARIANCE_TYPE"] in ["learned", "learned_range"],
            downsampling=CONFIG["DOWN_SAMPLING"],
        )
    elif CONFIG["MODEL"] == "unet3+":
        model = cdd_model.Unet3plus(
            baseDim=CONFIG["BASE_DIM"],
            dim_mults=CONFIG["DIM_MULTIPLIER"],
            numBlocks=CONFIG["NUM_BLOCKS"],
            numResBlocks=CONFIG["NUM_RES_BLOCKS"],
            attentionBlocks=CONFIG["ATTENTION_BLOCKS"],
            dropResBlockRate=CONFIG["DROP_RESBLOCK_RATE"],
            concat_filters=CONFIG["BASE_DIM"],
            diffusionChannels=cdd_helper.get_channels_from_format(CONFIG["DIFFUSION_FORMAT"]),
            learned_variance=CONFIG["VARIANCE_TYPE"] in ["learned", "learned_range"],
            downsampling=CONFIG["DOWN_SAMPLING"],
        )
    else:
        raise Exception(f'Undefined model provided: {CONFIG["MODEL"]}')

    diffusionModel = cdd_model.DiffusionModel(
        model=model,
        varianceType=CONFIG["VARIANCE_TYPE"],
        diffusionSteps=CONFIG["TIMESTEPS"],
        betaScheduleType=CONFIG["BETA_SCHEDULE"],
        lossWeighting=CONFIG["LOSS_WEIGHTING_TYPE"],
        lambdaVLB=CONFIG["LAMBDA_L_VLB"],
        mixedPrecission=CONFIG["USE_MIXED_PRECISION"],
        diffusionInputShapeChannels=cdd_helper.get_channels_from_format(CONFIG["DIFFUSION_FORMAT"]),
        diffusionInputShapeHeightWidth=CONFIG["IMG_HEIGHT_WIDTH"],
    )
    diffusionModel.compile(optimizer)
    diffusionModel.model.build(
        (*list(CONFIG["IMG_HEIGHT_WIDTH"]), cdd_helper.get_channels_from_format(CONFIG["CONDITION_FORMAT"])),
        (*list(CONFIG["IMG_HEIGHT_WIDTH"]), cdd_helper.get_channels_from_format(CONFIG["DIFFUSION_FORMAT"])),
    )
    diffusionModel.model.summary(line_length=100, expand_nested=True)

    # create our checkopint manager
    ckpt = tf.train.Checkpoint(model=diffusionModel.model, optimizer=diffusionModel.optimizer)

    # load from a previous checkpoint if it exists, else initialize the model from scratch
    if CONFIG["RESTORE_CHECKPOINT"]:
        ckpt.restore(CONFIG["CHECKPOINT_PATH_TO_RESTORE"])
        epoch_offset = int(CONFIG["CHECKPOINT_PATH_TO_RESTORE"].split("-")[-1])
        logging.info(f'Restored model from {CONFIG["CHECKPOINT_PATH_TO_RESTORE"]}')
    else:
        epoch_offset = 0
        logging.info("Initializing model from scratch.")

ckpt_manager = tf.train.CheckpointManager(ckpt, os.path.join(CONFIG["OUTDIR"], "checkpoints"), max_to_keep=10)

#############################################################
###### Training
#############################################################
cdd_helper.train(
    diffusionModel,
    train_ds,
    test_ds,
    globalBatchsize=CONFIG["GLOBAL_BATCH_SIZE"],
    epochs=CONFIG["EPOCHS"],
    ckpt_manager=ckpt_manager,
    epoch_offset=epoch_offset,
    testFrequency=CONFIG["TEST_FREQUENCY"],
    checkpointFrequency=CONFIG["CHECKPOINT_FREQUENCY"],
    run_output_dir=CONFIG["OUTDIR"],
    callbacks=cdd_helper.GetCallbacks(diffusionModel, CONFIG, test_ds),
    distributedTraining=CONFIG["DISTRIBUTED_TRAINING"],
)
